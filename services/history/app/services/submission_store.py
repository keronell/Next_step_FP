"""Submission records in the Dapr state store (replaces the Supabase `submissions` table).

Key schema (`||` is reserved by Dapr, so `:` separates segments):
    sub:{request_id}          -> full submission record (answers, recommendations,
                                 session_id, user_id, selected_career, selected_at,
                                 created_at)
    idx:session:{session_id}  -> [request_id, ...]   (anonymous correlation key)
    idx:user:{user_id}        -> [request_id, ...]   (claimed / authenticated)
    claim:{session_id}        -> [{"user_id", "at"}, ...]  (TTL'd claim windows)
    sel:{session_id}          -> {"career_id", "at"}       (TTL'd, latest click wins)
    del:{request_id}          -> {"at"}  (PERMANENT deletion tombstone: suppresses
                                 at-least-once redelivery from resurrecting a
                                 hard-deleted submission — see persist_submission.
                                 Never TTL'd: stream redelivery has no time bound.)

Everything raises DaprError upward — callers own the HTTP semantics (persistence
swallows, auth history routes translate to 503/500), same split as before.

Writes are idempotent so at-least-once pub/sub redelivery is safe: a record is
written only if its key is absent (a redelivered event can never un-claim a
submission), and index appends dedupe.

Concurrency: every read-modify-write (index appends, claim/selection field
updates) goes through _update — an etag compare-and-swap loop — and the initial
record write is create-only, so concurrent handlers (claim runs in the request
threadpool while events arrive on the loop; DEV-43 may run several history
replicas) merge instead of overwriting each other with stale whole-record copies.

Ordering races: pub/sub delivery is async and the `selections` topic has no
ordering guarantee against `submissions`, so a claim or selection can arrive
*before* the submission it targets exists. Both leave a short-lived marker
(TTL'd via Dapr ttlInSeconds) that persist_submission consults when the
submission finally lands. Time rules (the browser session id survives logout,
so a shared computer can interleave users within the TTL):

- A submission is claimable by the EARLIEST claim window whose `at` postdates
  its created_at (_resolve_claim). The claim marker is a CAS-appended LIST of
  windows: a later login's claim never replaces a pending earlier one, and each
  record resolves to its rightful claimant regardless of event/claim order.
  The same bound applies during the claim's own index walk — a record indexed
  concurrently but CREATED after the claim is never grabbed.
- A selection applies only to records created before its click time
  (selected_at, carried in the event), and records keep the applied
  selected_at so a stale/redelivered older selection can never overwrite a
  newer choice: last CLICK wins, not last delivery.

Marker TTL is garbage collection only — the time rules above are what scope a
marker's effect, so retention can (and does) far exceed any redelivery horizon.
"""
from datetime import datetime, timezone
from common.logging import get_logger
from common.dapr import (
    DaprConflict,
    DaprError,
    delete_state,
    get_bulk_state,
    get_state,
    get_state_with_etag,
    save_state,
)

logger = get_logger(__name__)

HISTORY_LIMIT = 20
# Markers are TIME-SCOPED, not TTL-scoped: _covers/_resolve_claim decide what a
# marker may touch, so expiry is pure garbage collection and can never cause —
# or prevent — a misattribution. It only needs to outlast the broker's real
# redelivery horizon (Redis Streams pending entries have NO upper bound), so be
# generous: a week covers any plausible outage while still self-cleaning.
MARKER_TTL_SECONDS = 7 * 24 * 3600


def _sub_key(request_id: str) -> str:
    return f"sub:{request_id}"


def _session_idx(session_id: str) -> str:
    return f"idx:session:{session_id}"


def _user_idx(user_id: str) -> str:
    return f"idx:user:{user_id}"


def _claim_marker(session_id: str) -> str:
    return f"claim:{session_id}"


def _sel_marker(session_id: str) -> str:
    return f"sel:{session_id}"


def _tombstone_key(request_id: str) -> str:
    return f"del:{request_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _covers(marker, record: dict) -> bool:
    """A marker applies only to records already submitted when it was written.

    Both timestamps are UTC ISO-8601 from datetime.isoformat(), so string
    comparison is chronological. Missing/malformed fields fail closed: a marker
    must PROVE the record was in flight, never guess.
    """
    if not isinstance(marker, dict):
        return False
    created_at = record.get("created_at")
    marked_at = marker.get("at")
    return bool(created_at and marked_at and created_at <= marked_at)


def _claim_windows(state) -> list[dict]:
    """Normalize the claim marker to a list of {"user_id", "at"} windows."""
    if isinstance(state, dict):  # transitional single-window shape
        state = [state]
    if not isinstance(state, list):
        return []
    return [w for w in state if isinstance(w, dict) and w.get("user_id") and w.get("at")]


def _resolve_claim(windows: list[dict], record: dict) -> str | None:
    """The rightful claimant of a record: the EARLIEST claim made after it was
    submitted. Later claims (a different login on the same browser) only cover
    records created after the earlier claims — never a pending predecessor's."""
    covering = [w for w in windows if _covers(w, record)]
    if not covering:
        return None
    return min(covering, key=lambda w: w["at"])["user_id"]


_CAS_RETRIES = 5


def _update(key: str, mutate, *, ttl_seconds: int | None = None):
    """Etag compare-and-swap loop: read, mutate, save-if-unchanged, else re-read.

    `mutate(value_or_None) -> new_value | None`; None means "condition no longer
    holds, nothing to write". Returns the newly saved value, or None when mutate
    declined — so callers can tell "I changed it" from "someone else already had".
    Raises DaprError after _CAS_RETRIES lost races — callers already own error
    semantics (subscribers answer RETRY, routes 500/swallow).
    """
    for _ in range(_CAS_RETRIES):
        value, etag = get_state_with_etag(key)
        new = mutate(value)
        if new is None:
            return None
        try:
            if etag is None:
                save_state(key, new, if_absent=True, ttl_seconds=ttl_seconds)
            else:
                save_state(key, new, etag=etag, ttl_seconds=ttl_seconds)
            return new
        except DaprConflict:
            continue  # someone else wrote first — re-read and re-apply
    raise DaprError(f"update({key}) still conflicting after {_CAS_RETRIES} attempts")


def _append_index(key: str, request_id: str) -> None:
    _update(
        key,
        lambda ids: (ids or []) + [request_id] if request_id not in (ids or []) else None,
    )


def _remove_from_index(key: str, request_id: str) -> None:
    _update(
        key,
        lambda ids: [i for i in ids if i != request_id] if ids and request_id in ids else None,
    )


def _purge(request_id: str, user_id, session_id) -> None:
    """Remove a submission record and its index entries. Idempotent, so a concurrent
    delete and a persist-undo (both calling this) converge on the deleted state.

    The RECORD (answers) is deleted FIRST — the hard-delete guarantee. Once it's gone
    get_user_submissions omits it (bulk-read skips missing keys), so index cleanup is
    best-effort: a dangling index entry is harmless and must NOT fail the delete after
    the record is already gone. If deleting the record itself fails we propagate — the
    caller 500s with everything intact and the row still visible for a retry, never
    the reverse (user-visible reference removed while the answers are retained)."""
    delete_state(_sub_key(request_id))
    try:
        if user_id:
            _remove_from_index(_user_idx(user_id), request_id)
        if session_id:
            _remove_from_index(_session_idx(session_id), request_id)
    except DaprError:
        logger.warning(
            "Index cleanup for %s failed after record delete — harmless dangling "
            "entry left (omitted from history; self-healed on any redelivery)",
            request_id,
        )


def persist_submission(record: dict) -> None:
    """Store one submission record + index it by session and (if present) user.

    Ends by reconciling claim/selection markers (see module docstring): the
    marker check runs AFTER the session-index append, and the racing operations
    write their marker BEFORE (claim) or fix up AFTER (selection) walking that
    index — so whichever side loses the race still sees the other's write.
    """
    request_id = record["request_id"]
    session_id = record.get("session_id")
    # A tombstone means the owner hard-deleted this submission. Without this check a
    # redelivered event (pub/sub is at-least-once) would find an absent sub: key,
    # treat it as a first delivery, and resurrect the record + its indexes after a
    # successful 204. Drop it instead — the subscriber ACKs, ending redelivery. (The
    # tombstone never expires — see delete_submission — so an arbitrarily late
    # redelivery is still caught; request_ids are unique, so it never blocks a new one.)
    if get_state(_tombstone_key(request_id)) is not None:
        # Tombstoned = deleted. If a record is still present — a delete whose purge
        # partially failed (record retained), or an earlier redelivery that recreated
        # it — complete the deletion now so a tombstoned submission can never keep a
        # live record. This makes a partially-failed delete recoverable: any
        # redelivery finishes it. Then drop (subscriber ACKs, ending redelivery).
        retained = get_state(_sub_key(request_id))
        if retained is not None:
            logger.info("Submission %s tombstoned but record present — purging", request_id)
            _purge(request_id, retained.get("user_id"), retained.get("session_id"))
        else:
            logger.info("Submission %s tombstoned — dropping redelivered event", request_id)
        return
    key = _sub_key(request_id)
    if get_state(key) is None:  # first write wins — redelivery can't clobber a claim
        try:
            save_state(key, record, if_absent=True)
        except DaprConflict:
            pass  # a concurrent delivery of the same event won; its copy is identical
    if session_id:
        _append_index(_session_idx(session_id), request_id)
    if record.get("user_id"):
        _append_index(_user_idx(record["user_id"]), request_id)
    # Post-create recheck — closes the check-then-create race with delete_submission:
    # a DELETE can write the tombstone AFTER the initial check above but around these
    # writes, so the initial guard alone can miss it and resurrect the record. If the
    # tombstone now exists, undo — deletion wins. _purge is idempotent, so this and
    # the concurrent delete converge on "deleted" regardless of interleaving; and a
    # DELETE whose tombstone lands after this recheck simply removes the record itself.
    if get_state(_tombstone_key(request_id)) is not None:
        logger.info("Submission %s tombstoned during persist — undoing recreate", request_id)
        _purge(request_id, record.get("user_id"), session_id)
        return
    if session_id:
        reconciled_owner = _reconcile_markers(request_id, session_id)
        # Post-reconcile recheck (P3): for a record that still exists, reconcile can
        # re-append the (possibly newly-claimed) owner's user index AFTER a concurrent
        # DELETE already removed it, stranding a permanent missing-record entry that
        # get_user_submissions reads but never prunes. If the tombstone now exists,
        # purge again — including the reconciled owner's index, which may differ from
        # the event's user_id (an anonymous submission claimed after it was delivered).
        if get_state(_tombstone_key(request_id)) is not None:
            logger.info("Submission %s tombstoned during reconcile — purging", request_id)
            _purge(request_id, record.get("user_id"), session_id)
            if reconciled_owner and reconciled_owner != record.get("user_id"):
                _remove_from_index(_user_idx(reconciled_owner), request_id)


def _reconcile_markers(request_id: str, session_id: str) -> str | None:
    """Apply a claim/selection that was delivered before this submission existed.
    Returns the user_id it (re-)indexed the record under, or None.

    Idempotent (re-reads the stored record, only fills absent fields) and
    CAS-protected, so redelivery and concurrent claim/selection walks merge
    instead of clobbering each other.
    """
    windows = _claim_windows(get_state(_claim_marker(session_id)))
    selection = get_state(_sel_marker(session_id))
    if not windows and not selection:
        return
    applied = {"owner": None}

    def _fill(record):
        applied["owner"] = None  # reset per attempt — CAS may re-run this
        if record is None:
            return None
        changed = False
        if record.get("user_id") is None:
            owner = _resolve_claim(windows, record)
            if owner:
                record["user_id"] = owner
                applied["owner"] = owner
                changed = True
        if (
            isinstance(selection, dict)
            and selection.get("career_id")
            and _covers(selection, record)
            and (record.get("selected_at") or "") < selection["at"]
        ):
            record["selected_career"] = selection["career_id"]
            record["selected_at"] = selection["at"]
            changed = True
        return record if changed else None

    stored = _update(_sub_key(request_id), _fill)
    if stored is not None and applied["owner"]:
        logger.info(
            "Submission %s: applied pending claim for user %s",
            request_id,
            applied["owner"],
        )
    if stored is None:
        # Nothing to change NOW — but a previous attempt may have stored the
        # owner and then died before indexing (we'd be here on its redelivery,
        # where _fill declines). Re-read and repair the index unconditionally.
        stored = get_state(_sub_key(request_id))
    if stored and stored.get("user_id"):
        _append_index(_user_idx(stored["user_id"]), request_id)
        return stored["user_id"]
    return None


def apply_selection(session_id: str, career_id: str, selected_at: str) -> int:
    """Set selected_career on the session's records that existed at click time
    (parity with the old UPDATE ... WHERE session_id=X, which could only see
    rows inserted before the click). Returns how many records were touched.

    selected_at is the CLICK time carried in the event — not consume time: a
    delayed selection event may be processed after a retake was submitted and
    indexed, and that retake must not inherit the old choice. The same bound
    scopes the marker (see _covers). The marker is written FIRST so a submission
    landing mid-walk can't miss it, and it expires via TTL rather than being
    deleted on success — deleting would re-lose the selection when an older
    record absorbed the walk while the just-submitted one was still in flight.
    """
    marker = {"career_id": career_id, "at": selected_at}

    def _newer_marker(current):
        # Last CLICK wins: a delayed/redelivered older selection event must not
        # regress the marker a newer click already wrote.
        if isinstance(current, dict) and (current.get("at") or "") >= selected_at:
            return None
        return marker

    _update(_sel_marker(session_id), _newer_marker, ttl_seconds=MARKER_TTL_SECONDS)
    touched = 0

    def _set_selection(record):
        if record is None or not _covers(marker, record):
            return None
        if (record.get("selected_at") or "") >= selected_at:
            return None  # record already carries a newer (or this same) click
        record["selected_career"] = career_id
        record["selected_at"] = selected_at
        return record

    for request_id in get_state(_session_idx(session_id)) or []:
        if _update(_sub_key(request_id), _set_selection) is not None:
            touched += 1
    return touched


def claim_sessions(user_id: str, session_id: str) -> int:
    """Link the session's anonymous records to their rightful claimant. Only
    records with no user_id are claimed (a record can't be re-claimed).
    Returns how many records the CALLER ended up owning.

    The claim window is APPENDED to the marker list first (never replacing a
    pending earlier claim): if a submission event is delivered between that
    write and the index walk, either this walk sees it or its
    persist_submission sees the marker — the claim can't fall through the gap.
    Each record then resolves to the earliest claim window that postdates its
    created_at (_resolve_claim), so an anonymous submission made AFTER a claim
    (same browser, possibly a different person post-logout) is never grabbed by
    it — not even by this walk racing a concurrent index append.
    """
    entry = {"user_id": user_id, "at": _now_iso()}
    windows = _claim_windows(
        _update(
            _claim_marker(session_id),
            lambda current: _claim_windows(current) + [entry],
            ttl_seconds=MARKER_TTL_SECONDS,
        )
    )

    def _set_owner(record):
        if record is None or record.get("user_id") is not None:
            return None  # missing or already claimed — leave untouched
        owner = _resolve_claim(windows, record)
        if owner is None:
            return None  # created after every claim window — stays anonymous
        record["user_id"] = owner
        return record

    claimed = 0
    for request_id in get_state(_session_idx(session_id)) or []:
        # _update returns non-None only when OUR mutate saved — exact count even
        # when a concurrent duplicate claim races this one. Index IMMEDIATELY:
        # deferring appends to after the loop would strand earlier claims if a
        # later record's update raises.
        stored = _update(_sub_key(request_id), _set_owner)
        if stored is not None:
            _append_index(_user_idx(stored["user_id"]), request_id)
            if stored["user_id"] == user_id:
                claimed += 1
        else:
            # Already owned — possibly by us, from an earlier claim that set the
            # owner but died before indexing. Repair the index if it's ours.
            record = get_state(_sub_key(request_id))
            if record is not None and record.get("user_id") == user_id:
                _append_index(_user_idx(user_id), request_id)
    return claimed


def get_user_submissions(user_id: str) -> list[dict]:
    """The user's most recent submissions, newest first, capped at HISTORY_LIMIT.

    # ponytail: fetches the whole index then trims — fine for quiz-app volumes;
    # cap the index itself if a user ever accumulates hundreds of submissions.
    """
    ids = get_state(_user_idx(user_id)) or []
    if not ids:
        return []
    records = get_bulk_state([_sub_key(rid) for rid in ids])
    ordered = sorted(
        records.values(), key=lambda r: r.get("created_at") or "", reverse=True
    )
    return ordered[:HISTORY_LIMIT]


def delete_submission(user_id: str, request_id: str) -> bool:
    """Hard-delete a submission the requesting user owns (DEV-75).

    Returns True when a record was removed, False when it doesn't exist or belongs
    to someone else — the caller maps False to 404, never revealing that another
    user's submission exists. Ownership is checked against the STORED record's
    user_id (not any client-supplied index), so a user can only ever delete their
    own submissions.

    A (permanent) tombstone is written FIRST so a submission event redelivered after
    this delete (at-least-once pub/sub) can't resurrect the record — persist_submission
    consults it. Then _purge deletes the record (answers) before its index entries, so
    a partial storage failure never removes the user-visible reference while retaining
    the record: either everything is still present (record delete failed → 500, row
    stays visible for a retry), or the record is gone and only a harmless dangling
    index entry may remain. And because the tombstone is permanent, any later
    redelivery finishes a partially-failed purge (see persist_submission), so the
    hard-delete guarantee holds even across storage errors.
    """
    record = get_state(_sub_key(request_id))
    if record is None or record.get("user_id") != user_id:
        return False
    # PERMANENT tombstone (no TTL): Redis Streams pending entries have no upper time
    # bound, so a redelivery could arrive arbitrarily late — a TTL'd marker that
    # expired first would let the deleted assessment resurface. request_ids are
    # unique and never reused, so one non-expiring del: key per deleted submission
    # can never suppress a genuinely new one (bounded by total deletions).
    save_state(_tombstone_key(request_id), {"at": _now_iso()})
    _purge(request_id, user_id, record.get("session_id"))
    return True
