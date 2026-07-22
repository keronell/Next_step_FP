"""submission_store: state-key schema + SQL-parity semantics over a versioned fake.

The store imports get_state/get_state_with_etag/save_state/get_bulk_state by
name, so monkeypatching submission_store.<fn> swaps the sidecar for an
in-memory store (same pattern the old Supabase tests used). The fake enforces
etag semantics — a stale etag or an if_absent collision raises DaprConflict —
so the CAS retry paths are actually exercised.
"""
import copy

import pytest

from app.services import submission_store
from common.dapr import DaprConflict, DaprError


class _FakeStateStore:
    """Dict-backed state store with etag (version) semantics and copy-on-read,
    mirroring how the sidecar returns deserialized copies."""

    def __init__(self):
        self.data: dict = {}
        self._versions: dict = {}

    def get(self, key):
        return copy.deepcopy(self.data.get(key))

    def get_with_etag(self, key):
        if key not in self.data:
            return None, None
        # .get: tests may seed .data directly without a version entry
        return copy.deepcopy(self.data[key]), str(self._versions.get(key, 0))

    def save(self, key, value, ttl_seconds=None, etag=None, if_absent=False):
        if if_absent and key in self.data:
            raise DaprConflict(f"{key} already exists")
        if etag is not None and etag != str(self._versions.get(key)):
            raise DaprConflict(f"{key} etag mismatch")
        self.data[key] = copy.deepcopy(value)
        self._versions[key] = self._versions.get(key, 0) + 1

    def bulk(self, keys):
        return {k: copy.deepcopy(self.data[k]) for k in keys if k in self.data}

    def delete(self, key):
        self.data.pop(key, None)
        self._versions.pop(key, None)


@pytest.fixture
def store(monkeypatch) -> _FakeStateStore:
    fake = _FakeStateStore()
    monkeypatch.setattr(submission_store, "get_state", fake.get)
    monkeypatch.setattr(submission_store, "get_state_with_etag", fake.get_with_etag)
    monkeypatch.setattr(submission_store, "save_state", fake.save)
    monkeypatch.setattr(submission_store, "get_bulk_state", fake.bulk)
    monkeypatch.setattr(submission_store, "delete_state", fake.delete)
    return fake


@pytest.fixture
def state(store) -> dict:
    return store.data


def _record(rid: str, session_id="sess-1", user_id=None, created_at="2026-07-16T10:00:00+00:00"):
    return {
        "request_id": rid,
        "answers": {"q1": 1},
        "recommendations": [{"id": "frontend"}],
        "session_id": session_id,
        "user_id": user_id,
        "selected_career": None,
        "created_at": created_at,
    }


def test_persist_indexes_by_session_and_user(state):
    submission_store.persist_submission(_record("r1", user_id="u1"))
    assert state["sub:r1"]["request_id"] == "r1"
    assert state["idx:session:sess-1"] == ["r1"]
    assert state["idx:user:u1"] == ["r1"]


def test_persist_without_user_skips_user_index(state):
    submission_store.persist_submission(_record("r1"))
    assert "idx:user:None" not in state
    assert [k for k in state if k.startswith("idx:user:")] == []


def test_persist_is_idempotent_and_first_write_wins(state):
    submission_store.persist_submission(_record("r1"))
    state["sub:r1"]["user_id"] = "u1"  # a later claim mutates the record...
    submission_store.persist_submission(_record("r1"))  # ...redelivery must not undo it
    assert state["sub:r1"]["user_id"] == "u1"
    assert state["idx:session:sess-1"] == ["r1"]  # no duplicate index entries


_CLICK = "2026-07-17T00:00:00+00:00"  # after _record's default created_at


def test_apply_selection_touches_all_session_records(state):
    submission_store.persist_submission(_record("r1"))
    submission_store.persist_submission(_record("r2"))
    touched = submission_store.apply_selection("sess-1", "frontend", _CLICK)
    assert touched == 2
    assert state["sub:r1"]["selected_career"] == "frontend"
    assert state["sub:r2"]["selected_career"] == "frontend"


def test_apply_selection_unknown_session_leaves_marker(state):
    # Nothing to touch: the submission event may still be in flight, so a
    # TTL'd marker stamped with the CLICK time is left for arrival.
    assert submission_store.apply_selection("nope", "frontend", _CLICK) == 0
    assert state["sel:nope"] == {"career_id": "frontend", "at": _CLICK}


def test_selection_walk_skips_records_submitted_after_click(state):
    # A delayed selection event processed after a retake landed: only the
    # submission that existed at click time gets the choice.
    submission_store.persist_submission(_record("r1", created_at="2026-07-16T10:00:00+00:00"))
    submission_store.persist_submission(_record("r2", created_at="2026-07-18T10:00:00+00:00"))
    touched = submission_store.apply_selection("sess-1", "frontend", _CLICK)
    assert touched == 1
    assert state["sub:r1"]["selected_career"] == "frontend"
    assert state["sub:r2"]["selected_career"] is None


# --- pub/sub ordering races (marker reconciliation) --------------------------

def test_claim_before_delivery_applies_on_arrival(state):
    # Login + claim happen while the submission event is still in flight.
    assert submission_store.claim_sessions("u1", "sess-1") == 0
    submission_store.persist_submission(_record("r1"))  # anonymous arrival
    assert state["sub:r1"]["user_id"] == "u1"
    assert state["idx:user:u1"] == ["r1"]


def test_selection_before_delivery_applies_on_arrival(state):
    # /select outruns the submission event (different topics, no ordering).
    submission_store.apply_selection("sess-1", "frontend", _CLICK)
    submission_store.persist_submission(_record("r1"))
    assert state["sub:r1"]["selected_career"] == "frontend"


def test_claim_marker_never_overrides_authenticated_record(state):
    submission_store.claim_sessions("u1", "sess-1")
    submission_store.persist_submission(_record("r1", user_id="someone-else"))
    assert state["sub:r1"]["user_id"] == "someone-else"
    assert "idx:user:u1" not in state


def _clock(monkeypatch, times: list[str]):
    """Feed claim_sessions a deterministic sequence of _now_iso values."""
    seq = iter(times)
    monkeypatch.setattr(submission_store, "_now_iso", lambda: next(seq))


def test_claim_marker_ignores_submissions_made_after_the_claim(state, monkeypatch):
    # Session ids survive logout: an anonymous submission AFTER the claim (maybe
    # a different person on the same browser) must stay unclaimed by that claim.
    _clock(monkeypatch, ["2026-07-17T10:00:00+00:00", "2026-07-17T12:00:00+00:00"])
    submission_store.claim_sessions("u1", "sess-1")  # claim at 10:00
    submission_store.persist_submission(
        _record("r1", created_at="2026-07-17T11:00:00+00:00")  # submitted 11:00
    )
    assert state["sub:r1"]["user_id"] is None
    assert "idx:user:u1" not in state
    # ...and the rightful owner (claiming at 12:00, after submitting) gets it.
    assert submission_store.claim_sessions("u2", "sess-1") == 1
    assert state["sub:r1"]["user_id"] == "u2"
    assert state["idx:user:u2"] == ["r1"]


def test_claim_walk_respects_claim_time_for_late_indexed_records(state, monkeypatch):
    # A record CREATED after the claim but INDEXED before the walk reads the
    # index must not be grabbed — the walk enforces the same bound as reconcile.
    state.update(
        {
            "sub:r1": _record("r1", created_at="2026-07-17T11:00:00+00:00"),
            "idx:session:sess-1": ["r1"],
        }
    )
    _clock(monkeypatch, ["2026-07-17T10:00:00+00:00"])  # claim predates creation
    assert submission_store.claim_sessions("u1", "sess-1") == 0
    assert state["sub:r1"]["user_id"] is None


def test_earliest_covering_claim_wins_over_later_claimant(state, monkeypatch):
    # A claims while their submission event is in flight; B claims the same
    # browser session before it arrives. The record predates BOTH claims, so it
    # belongs to A (earliest covering window), not to B who claimed last.
    _clock(monkeypatch, ["2026-07-17T10:00:00+00:00", "2026-07-17T10:05:00+00:00"])
    submission_store.claim_sessions("uA", "sess-1")
    submission_store.claim_sessions("uB", "sess-1")
    submission_store.persist_submission(
        _record("r1", created_at="2026-07-17T09:59:00+00:00")
    )
    assert state["sub:r1"]["user_id"] == "uA"
    assert state["idx:user:uA"] == ["r1"]
    assert "idx:user:uB" not in state


def test_record_between_claim_windows_goes_to_later_claimant(state, monkeypatch):
    # B's anonymous quiz (after A logged out, before B logged in) belongs to B.
    _clock(monkeypatch, ["2026-07-17T10:00:00+00:00", "2026-07-17T10:30:00+00:00"])
    submission_store.claim_sessions("uA", "sess-1")
    submission_store.claim_sessions("uB", "sess-1")
    submission_store.persist_submission(
        _record("r1", created_at="2026-07-17T10:15:00+00:00")  # between the claims
    )
    assert state["sub:r1"]["user_id"] == "uB"
    assert state["idx:user:uB"] == ["r1"]


def test_selection_marker_ignores_submissions_made_after_the_selection(state):
    # A retake after picking a career must not inherit the previous selection.
    submission_store.apply_selection("sess-1", "frontend", _CLICK)
    future = _record("r1", created_at="2999-01-01T00:00:00+00:00")
    submission_store.persist_submission(future)
    assert state["sub:r1"]["selected_career"] is None


def test_stale_selection_event_never_overwrites_newer_choice(state):
    # User clicks A then B; A's event is delivered/redelivered AFTER B applied.
    submission_store.persist_submission(_record("r1"))
    submission_store.apply_selection("sess-1", "career-b", "2026-07-17T02:00:00+00:00")
    assert state["sub:r1"]["selected_career"] == "career-b"
    # stale A (clicked earlier) arrives late:
    touched = submission_store.apply_selection("sess-1", "career-a", "2026-07-17T01:00:00+00:00")
    assert touched == 0
    assert state["sub:r1"]["selected_career"] == "career-b"  # record kept newer click
    assert state["sel:sess-1"]["career_id"] == "career-b"  # marker not regressed
    # exact redelivery of B is a no-op, not a double-apply:
    assert submission_store.apply_selection("sess-1", "career-b", "2026-07-17T02:00:00+00:00") == 0


def test_reconcile_applies_latest_selection_to_in_flight_record(state):
    # Clicks A then B while the submission event is still in flight: the record
    # must arrive with B (the marker kept the latest click).
    submission_store.apply_selection("sess-1", "career-a", "2026-07-17T01:00:00+00:00")
    submission_store.apply_selection("sess-1", "career-b", "2026-07-17T02:00:00+00:00")
    submission_store.persist_submission(_record("r1"))
    assert state["sub:r1"]["selected_career"] == "career-b"
    assert state["sub:r1"]["selected_at"] == "2026-07-17T02:00:00+00:00"


# --- CAS (etag) concurrency ---------------------------------------------------

def test_concurrent_index_appends_both_survive(store, monkeypatch):
    # A second writer sneaks in between this append's read and save: the stale
    # etag must trigger a retry that merges, not a lost entry.
    original = store.get_with_etag
    raced = {"done": False}

    def racy_get(key):
        value, etag = original(key)
        if key == "idx:session:sess-1" and not raced["done"]:
            raced["done"] = True
            store.save(key, (value or []) + ["r-other"])  # bumps the version
        return value, etag

    monkeypatch.setattr(submission_store, "get_state_with_etag", racy_get)
    submission_store._append_index("idx:session:sess-1", "r1")
    assert set(store.data["idx:session:sess-1"]) == {"r-other", "r1"}


def test_concurrent_claim_and_selection_merge(store, monkeypatch):
    # A selection lands on the record between the claim's read and save; the
    # claim must retry and keep BOTH fields (no stale whole-record overwrite).
    submission_store.persist_submission(_record("r1"))
    original = store.get_with_etag
    raced = {"done": False}

    def racy_get(key):
        value, etag = original(key)
        if key == "sub:r1" and not raced["done"]:
            raced["done"] = True
            selected = copy.deepcopy(store.data["sub:r1"])
            selected["selected_career"] = "frontend"
            store.save(key, selected)  # concurrent selection write
        return value, etag

    monkeypatch.setattr(submission_store, "get_state_with_etag", racy_get)
    assert submission_store.claim_sessions("u1", "sess-1") == 1
    final = store.data["sub:r1"]
    assert final["user_id"] == "u1"
    assert final["selected_career"] == "frontend"  # survived the claim's save


def test_reconcile_redelivery_repairs_missing_user_index(store):
    # A prior reconcile stored the claimed owner but died before indexing.
    # Redelivery's _fill declines (owner already set) — the heal path must
    # still append the user index.
    submission_store.claim_sessions("u1", "sess-1")  # marker only, no records yet
    store.data["sub:r1"] = _record("r1", user_id="u1")  # owner set, index lost
    store.data["idx:session:sess-1"] = ["r1"]
    assert "idx:user:u1" not in store.data
    submission_store.persist_submission(_record("r1"))  # anonymous redelivery
    assert store.data["idx:user:u1"] == ["r1"]


def test_claim_repairs_index_for_already_owned_records(store):
    # Earlier claim set the owner but failed before indexing; re-claiming must
    # repair the index even though no record is newly claimed.
    store.data["sub:r1"] = _record("r1", user_id="u1")
    store.data["idx:session:sess-1"] = ["r1"]
    assert submission_store.claim_sessions("u1", "sess-1") == 0  # nothing NEW
    assert store.data["idx:user:u1"] == ["r1"]


def test_claim_indexes_each_record_before_next(store, monkeypatch):
    # A failure on the SECOND record must not strand the first one's index entry.
    submission_store.persist_submission(_record("r1"))
    submission_store.persist_submission(_record("r2"))
    original = store.get_with_etag

    def failing_get(key):
        if key == "sub:r2":
            raise submission_store.DaprError("sidecar hiccup")
        return original(key)

    monkeypatch.setattr(submission_store, "get_state_with_etag", failing_get)
    with pytest.raises(submission_store.DaprError):
        submission_store.claim_sessions("u1", "sess-1")
    assert store.data["idx:user:u1"] == ["r1"]  # r1 indexed despite r2 failing
    assert store.data["sub:r1"]["user_id"] == "u1"


def test_persist_redelivery_race_cannot_unclaim(store, monkeypatch):
    # Two deliveries of the same event: the second's create-only save loses the
    # race (record exists) and must not clobber a claim applied in between.
    submission_store.persist_submission(_record("r1"))
    submission_store.claim_sessions("u1", "sess-1")
    # Redelivery: get_state sees None *before* the first write... simulate the
    # worst interleaving by forcing the absent read, then the create-only save.
    monkeypatch.setattr(submission_store, "get_state", lambda key: (
        None if key == "sub:r1" else store.get(key)
    ))
    submission_store.persist_submission(_record("r1"))  # anonymous duplicate
    assert store.data["sub:r1"]["user_id"] == "u1"  # claim survived


def test_claim_skips_already_claimed_records(state):
    submission_store.persist_submission(_record("r1"))
    submission_store.persist_submission(_record("r2", user_id="someone-else"))
    claimed = submission_store.claim_sessions("u1", "sess-1")
    assert claimed == 1
    assert state["sub:r1"]["user_id"] == "u1"
    assert state["sub:r2"]["user_id"] == "someone-else"  # not re-claimed
    assert state["idx:user:u1"] == ["r1"]
    # Claiming again is a no-op (idempotent under retries / double-clicks).
    assert submission_store.claim_sessions("u1", "sess-1") == 0
    assert state["idx:user:u1"] == ["r1"]


def test_user_submissions_newest_first_capped(state):
    for i in range(25):
        submission_store.persist_submission(
            _record(f"r{i}", user_id="u1", created_at=f"2026-07-16T10:00:{i:02d}+00:00")
        )
    result = submission_store.get_user_submissions("u1")
    assert len(result) == submission_store.HISTORY_LIMIT
    assert result[0]["request_id"] == "r24"  # newest first
    assert result[-1]["request_id"] == "r5"


def test_user_submissions_drops_missing_records(state):
    submission_store.persist_submission(_record("r1", user_id="u1"))
    submission_store.persist_submission(_record("r2", user_id="u1"))
    del state["sub:r1"]  # index points at a vanished record
    result = submission_store.get_user_submissions("u1")
    assert [r["request_id"] for r in result] == ["r2"]


def test_user_submissions_empty_for_unknown_user(state):
    assert submission_store.get_user_submissions("nobody") == []


# ── delete_submission (DEV-75) ────────────────────────────────────────────────

def test_delete_submission_removes_record_and_indexes(state):
    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))
    assert submission_store.delete_submission("u1", "r1") is True
    assert "sub:r1" not in state
    assert state["idx:user:u1"] == []
    assert state["idx:session:s1"] == []
    assert submission_store.get_user_submissions("u1") == []


def test_delete_submission_only_targets_the_named_record(state):
    submission_store.persist_submission(_record("r1", user_id="u1"))
    submission_store.persist_submission(_record("r2", user_id="u1"))
    assert submission_store.delete_submission("u1", "r1") is True
    assert "sub:r1" not in state
    assert state["sub:r2"]["request_id"] == "r2"
    assert state["idx:user:u1"] == ["r2"]


def test_delete_submission_missing_returns_false(state):
    assert submission_store.delete_submission("u1", "nope") is False


def test_delete_submission_wrong_owner_refused(state):
    # A user cannot delete another user's submission: refused AND left untouched.
    submission_store.persist_submission(_record("r1", user_id="owner"))
    assert submission_store.delete_submission("attacker", "r1") is False
    assert state["sub:r1"]["request_id"] == "r1"          # record still present
    assert state["idx:user:owner"] == ["r1"]              # owner's index intact
    assert "idx:user:attacker" not in state


def test_delete_submission_anonymous_record_not_owned(state):
    # An unclaimed (anonymous) submission has user_id=None — no logged-in user owns
    # it, so a delete keyed on a real user id is refused.
    submission_store.persist_submission(_record("r1", user_id=None))
    assert submission_store.delete_submission("u1", "r1") is False
    assert state["sub:r1"]["request_id"] == "r1"


def test_delete_writes_tombstone(state):
    submission_store.persist_submission(_record("r1", user_id="u1"))
    submission_store.delete_submission("u1", "r1")
    assert state["del:r1"]["at"]  # tombstone recorded


def test_redelivery_after_delete_does_not_resurrect(state):
    # The core durability guarantee: an at-least-once submission event redelivered
    # AFTER a successful delete must not recreate the record or re-index it.
    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))
    assert submission_store.delete_submission("u1", "r1") is True

    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))
    assert "sub:r1" not in state
    assert state["idx:user:u1"] == []
    assert state["idx:session:s1"] == []
    assert submission_store.get_user_submissions("u1") == []


def test_tombstone_does_not_block_a_different_submission(state):
    # request_ids are unique per submission, so a tombstone only ever suppresses its
    # own redelivery — a genuinely new submission still persists.
    submission_store.persist_submission(_record("r1", user_id="u1"))
    submission_store.delete_submission("u1", "r1")
    submission_store.persist_submission(_record("r2", session_id="s1", user_id="u1"))
    assert state["sub:r2"]["request_id"] == "r2"
    assert state["idx:user:u1"] == ["r2"]


def test_persist_undoes_recreate_when_tombstoned_mid_persist(store, state, monkeypatch):
    # Simulate the check-then-create race: a DELETE lands (writes the tombstone)
    # AFTER persist's initial tombstone check but as it writes the record. The
    # post-create recheck must observe the tombstone and undo the recreate.
    real_save = submission_store.save_state  # the fake's save (installed by `store`)

    def save_then_delete(key, value, **kw):
        real_save(key, value, **kw)
        if key == "sub:r1" and "del:r1" not in state:
            real_save("del:r1", {"at": "2026-01-01T00:00:00+00:00"})  # concurrent delete

    monkeypatch.setattr(submission_store, "save_state", save_then_delete)
    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))

    assert "sub:r1" not in state                 # recreate was undone
    assert state.get("idx:user:u1", []) == []
    assert state.get("idx:session:s1", []) == []
    assert submission_store.get_user_submissions("u1") == []


def test_post_reconcile_recheck_prunes_stale_user_index(store, state, monkeypatch):
    # An anonymous submission (user_id=None) with a pending claim: reconcile applies
    # the claim and re-appends the CLAIMANT's user index. Simulate a DELETE landing
    # (writes the tombstone) exactly as that re-append happens — the post-reconcile
    # recheck must prune the stale idx:user entry (which _purge alone would miss,
    # since the event's user_id is None but the reconciled owner is the claimant).
    state["claim:s1"] = [{"user_id": "u1", "at": "2026-07-16T11:00:00+00:00"}]

    real_append = submission_store._append_index

    def append_then_delete(key, request_id):
        real_append(key, request_id)
        if key == "idx:user:u1" and "del:r1" not in state:
            state["del:r1"] = {"at": "2026-07-16T12:00:00+00:00"}  # concurrent DELETE

    monkeypatch.setattr(submission_store, "_append_index", append_then_delete)
    submission_store.persist_submission(
        _record("r1", session_id="s1", user_id=None, created_at="2026-07-16T10:00:00+00:00")
    )

    assert state.get("idx:user:u1", []) == []    # no permanent dangling entry
    assert "sub:r1" not in state
    assert submission_store.get_user_submissions("u1") == []


def test_delete_removes_record_even_if_index_cleanup_fails(store, state, monkeypatch):
    # The hard-delete guarantee: the record (answers) must be gone even if index
    # cleanup fails afterwards. The delete still succeeds; the dangling index entry
    # is harmless (get_user_submissions omits the missing record).
    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))

    def boom(*a, **k):
        raise DaprError("index store down")

    monkeypatch.setattr(submission_store, "_remove_from_index", boom)
    assert submission_store.delete_submission("u1", "r1") is True
    assert "sub:r1" not in state                 # answers gone — guarantee holds
    assert submission_store.get_user_submissions("u1") == []


def test_delete_record_failure_leaves_everything_for_retry(store, state, monkeypatch):
    # If the record delete itself fails, we propagate (caller 500s) with the record
    # AND its index intact — the row stays visible so the user can retry, never
    # hidden-but-retained.
    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))

    def boom(*a, **k):
        raise DaprError("record store down")

    monkeypatch.setattr(submission_store, "delete_state", boom)
    with pytest.raises(DaprError):
        submission_store.delete_submission("u1", "r1")
    assert state["sub:r1"]["request_id"] == "r1"   # still present
    assert state["idx:user:u1"] == ["r1"]          # still visible for a retry


def test_redelivery_self_heals_partially_deleted_record(store, state):
    # A delete whose purge partially failed: tombstone written, but the record +
    # index survived. A later redelivery must finish the deletion, not just drop.
    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))
    state["del:r1"] = {"at": "2026-01-01T00:00:00+00:00"}  # tombstone, record retained
    assert "sub:r1" in state

    submission_store.persist_submission(_record("r1", session_id="s1", user_id="u1"))
    assert "sub:r1" not in state
    assert state.get("idx:user:u1", []) == []
    assert state.get("idx:session:s1", []) == []


# ── DEV-75 follow-up: a failed index cleanup must self-heal on redelivery ──────

def test_redelivery_prunes_index_left_dangling_by_a_failed_purge(store):
    """_purge deletes the record first and cleans indexes best-effort. If that
    cleanup fails the id stays in the index forever: the redelivery path saw the
    record already absent and returned without repairing it, so the index grew
    without bound (get_user_submissions bulk-reads every id in it)."""
    record = {
        "request_id": "r-dangle",
        "answers": {"q1": 1},
        "recommendations": [],
        "session_id": "sess-d",
        "user_id": "user-d",
        "created_at": "2026-07-20T10:00:00+00:00",
    }
    submission_store.persist_submission(record)
    assert "r-dangle" in (submission_store.get_state("idx:user:user-d") or [])

    # Delete, but make index cleanup fail — the dangling-entry scenario.
    real_remove = submission_store._remove_from_index
    submission_store._remove_from_index = lambda *a, **k: (_ for _ in ()).throw(DaprError("index down"))
    try:
        assert submission_store.delete_submission("user-d", "r-dangle") is True
    finally:
        submission_store._remove_from_index = real_remove

    assert submission_store.get_state("sub:r-dangle") is None          # record gone
    assert "r-dangle" in (submission_store.get_state("idx:user:user-d") or [])   # index stale

    # At-least-once pub/sub redelivers the original event -> must self-heal.
    submission_store.persist_submission(record)
    assert submission_store.get_state("sub:r-dangle") is None          # not resurrected
    assert "r-dangle" not in (submission_store.get_state("idx:user:user-d") or [])
    assert "r-dangle" not in (submission_store.get_state("idx:session:sess-d") or [])


def test_redelivery_prunes_claimed_submission_via_tombstone_owner(store):
    """A CLAIMED submission was indexed under a user its event never mentioned
    (user_id=None at publish time), so the event alone can't identify the index —
    the tombstone has to carry the owner."""
    event = {
        "request_id": "r-claimed",
        "answers": {"q1": 1},
        "recommendations": [],
        "session_id": "sess-c",
        "user_id": None,
        "created_at": "2026-07-20T10:00:00+00:00",
    }
    submission_store.persist_submission(event)
    submission_store.claim_sessions("user-c", "sess-c")
    assert "r-claimed" in (submission_store.get_state("idx:user:user-c") or [])

    real_remove = submission_store._remove_from_index
    submission_store._remove_from_index = lambda *a, **k: (_ for _ in ()).throw(DaprError("index down"))
    try:
        assert submission_store.delete_submission("user-c", "r-claimed") is True
    finally:
        submission_store._remove_from_index = real_remove

    submission_store.persist_submission(event)   # redelivery
    assert "r-claimed" not in (submission_store.get_state("idx:user:user-c") or [])
