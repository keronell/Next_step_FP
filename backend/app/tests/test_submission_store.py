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
from app.services.dapr_client import DaprConflict


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


@pytest.fixture
def store(monkeypatch) -> _FakeStateStore:
    fake = _FakeStateStore()
    monkeypatch.setattr(submission_store, "get_state", fake.get)
    monkeypatch.setattr(submission_store, "get_state_with_etag", fake.get_with_etag)
    monkeypatch.setattr(submission_store, "save_state", fake.save)
    monkeypatch.setattr(submission_store, "get_bulk_state", fake.bulk)
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
