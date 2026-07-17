"""Dapr subscriber endpoints: subscription manifest + CloudEvents handling.

Events arrive as CloudEvents envelopes (payload under `data`). The handlers ack
with {"status": "SUCCESS"}, ask for redelivery with RETRY on state-store errors,
and DROP malformed events.
"""
from app.api.routes import subscriptions
from app.services import submission_store
from app.services.dapr_client import DaprError


def _envelope(data: dict) -> dict:
    """Minimal CloudEvents 1.0 envelope as the sidecar delivers it."""
    return {
        "id": "evt-1",
        "source": "nextstep-backend",
        "type": "com.dapr.event.sent",
        "specversion": "1.0",
        "datacontenttype": "application/json",
        "data": data,
    }


# --- /dapr/subscribe ---------------------------------------------------------

def test_subscribe_empty_when_disabled(client_with_repo):
    r = client_with_repo.get("/dapr/subscribe")
    assert r.status_code == 200
    assert r.json() == []


def test_subscribe_lists_both_topics(client_with_repo, monkeypatch):
    monkeypatch.setattr(subscriptions, "enabled", lambda: True)
    r = client_with_repo.get("/dapr/subscribe")
    subs = r.json()
    assert {s["topic"] for s in subs} == {"submissions", "selections"}
    routes = {s["topic"]: s["routes"]["default"] for s in subs}
    assert routes["submissions"] == "/events/submissions"
    assert routes["selections"] == "/events/selections"
    assert all(s["pubsubname"] == "pubsub" for s in subs)


# --- /events/submissions -----------------------------------------------------

def test_submission_event_persists_and_acks(client_with_repo, monkeypatch):
    stored = []
    monkeypatch.setattr(submission_store, "persist_submission", lambda rec: stored.append(rec))
    r = client_with_repo.post(
        "/events/submissions", json=_envelope({"request_id": "r1", "session_id": "s1"})
    )
    assert r.status_code == 200
    assert r.json() == {"status": "SUCCESS"}
    assert stored[0]["request_id"] == "r1"


def test_submission_event_without_request_id_dropped(client_with_repo, monkeypatch):
    monkeypatch.setattr(
        submission_store,
        "persist_submission",
        lambda rec: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    r = client_with_repo.post("/events/submissions", json=_envelope({"session_id": "s1"}))
    assert r.json() == {"status": "DROP"}


def test_poison_payloads_are_dropped_not_500(client_with_repo, monkeypatch):
    # A raised handler would 500 and make Dapr redeliver the poison forever.
    for fn in ("persist_submission", "apply_selection"):
        monkeypatch.setattr(
            submission_store, fn,
            lambda *a: (_ for _ in ()).throw(AssertionError("must not be called")),
        )
    for path in ("/events/submissions", "/events/selections"):
        for body in ([1, 2], "hi", None, {"data": "not-a-dict"}, {"data": [1]}):
            r = client_with_repo.post(path, json=body)
            assert (r.status_code, r.json()) == (200, {"status": "DROP"}), (path, body)
        r = client_with_repo.post(
            path, content=b"{not json", headers={"Content-Type": "application/json"}
        )
        assert (r.status_code, r.json()) == (200, {"status": "DROP"}), (path, "bad json")
    # Correct envelope, wrong field TYPES — truthiness alone would let these
    # reach string comparisons and 500 into infinite redelivery.
    typed = [
        ("/events/submissions", {"request_id": ["r1"]}),
        ("/events/submissions", {"request_id": "r1", "created_at": {"t": 1}}),
        ("/events/submissions", {"request_id": "r1", "session_id": 7}),
        ("/events/selections", {"session_id": "s1", "career_id": "x", "selected_at": [1]}),
        ("/events/selections", {"session_id": 5, "career_id": "x", "selected_at": "t"}),
    ]
    for path, data in typed:
        r = client_with_repo.post(path, json=_envelope(data))
        assert (r.status_code, r.json()) == (200, {"status": "DROP"}), (path, data)


def test_unexpected_handler_error_drops_instead_of_looping(client_with_repo, monkeypatch):
    # A deterministic bug (non-DaprError) must DROP — redelivery can't heal it.
    monkeypatch.setattr(
        submission_store,
        "persist_submission",
        lambda rec: (_ for _ in ()).throw(TypeError("boom")),
    )
    r = client_with_repo.post("/events/submissions", json=_envelope({"request_id": "r1"}))
    assert (r.status_code, r.json()) == (200, {"status": "DROP"})


def test_submission_event_store_error_requests_retry(client_with_repo, monkeypatch):
    def _boom(rec):
        raise DaprError("state store down")

    monkeypatch.setattr(submission_store, "persist_submission", _boom)
    r = client_with_repo.post("/events/submissions", json=_envelope({"request_id": "r1"}))
    assert r.json() == {"status": "RETRY"}


# --- /events/selections ------------------------------------------------------

_SEL_EVENT = {
    "session_id": "s1",
    "career_id": "frontend",
    "selected_at": "2026-07-17T09:00:00+00:00",
}


def test_selection_event_applies_and_acks(client_with_repo, monkeypatch):
    calls = []
    monkeypatch.setattr(
        submission_store,
        "apply_selection",
        lambda session_id, career_id, selected_at: calls.append(
            (session_id, career_id, selected_at)
        )
        or 1,
    )
    r = client_with_repo.post("/events/selections", json=_envelope(_SEL_EVENT))
    assert r.json() == {"status": "SUCCESS"}
    assert calls == [("s1", "frontend", _SEL_EVENT["selected_at"])]


def test_selection_event_missing_fields_dropped(client_with_repo):
    r = client_with_repo.post("/events/selections", json=_envelope({"career_id": "frontend"}))
    assert r.json() == {"status": "DROP"}


def test_selection_event_without_click_time_dropped(client_with_repo, monkeypatch):
    # Without selected_at the selection can't be scoped in time — fail closed.
    monkeypatch.setattr(
        submission_store,
        "apply_selection",
        lambda *a: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    r = client_with_repo.post(
        "/events/selections", json=_envelope({"session_id": "s1", "career_id": "frontend"})
    )
    assert r.json() == {"status": "DROP"}


def test_selection_event_store_error_requests_retry(client_with_repo, monkeypatch):
    def _boom(session_id, career_id, selected_at):
        raise DaprError("state store down")

    monkeypatch.setattr(submission_store, "apply_selection", _boom)
    r = client_with_repo.post("/events/selections", json=_envelope(_SEL_EVENT))
    assert r.json() == {"status": "RETRY"}


# --- sidecar token gate (APP_API_TOKEN) --------------------------------------

def test_events_reject_missing_or_wrong_token(client_with_repo, monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "sidecar-secret")
    from app.core.config import get_settings

    get_settings.cache_clear()
    r = client_with_repo.post("/events/submissions", json=_envelope({"request_id": "r1"}))
    assert r.status_code == 401
    r = client_with_repo.post(
        "/events/submissions",
        json=_envelope({"request_id": "r1"}),
        headers={"dapr-api-token": "wrong"},
    )
    assert r.status_code == 401
    r = client_with_repo.get("/dapr/subscribe")
    assert r.status_code == 401  # manifest is token-gated too


def test_events_accept_correct_token(client_with_repo, monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "sidecar-secret")
    from app.core.config import get_settings

    get_settings.cache_clear()
    stored = []
    monkeypatch.setattr(submission_store, "persist_submission", lambda rec: stored.append(rec))
    r = client_with_repo.post(
        "/events/submissions",
        json=_envelope({"request_id": "r1"}),
        headers={"dapr-api-token": "sidecar-secret"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "SUCCESS"}
    assert stored[0]["request_id"] == "r1"
