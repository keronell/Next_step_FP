"""Persistence is best-effort: Dapr disabled => no publish, errors => swallowed,
route still 200. The routes call save_submission/save_selection via BackgroundTasks
(the decoupling lives in the pub/sub broker), and mint created_at/selected_at at
request time — a late-running background task must never shift them."""
from app.services import persistence
from app.services.dapr_client import DaprError

_T = "2026-07-17T09:00:00+00:00"


def test_save_submission_noop_when_disabled(monkeypatch):
    # Default test settings have DAPR_ENABLED=false => no publish attempt, no raise.
    published = []
    monkeypatch.setattr(persistence, "publish", lambda topic, data: published.append(topic))
    persistence.save_submission("req1", {"q1": 1}, [{"id": "frontend"}], None, None, _T)
    assert published == []


def test_save_selection_noop_when_disabled(monkeypatch):
    published = []
    monkeypatch.setattr(persistence, "publish", lambda topic, data: published.append(topic))
    persistence.save_selection("sess1", "frontend", _T)
    assert published == []


def test_save_submission_publishes_full_record(monkeypatch):
    monkeypatch.setattr(persistence, "enabled", lambda: True)
    events = []
    monkeypatch.setattr(persistence, "publish", lambda topic, data: events.append((topic, data)))
    persistence.save_submission(
        "req2", {"q1": 1}, [{"id": "frontend"}], "sess-2", "u1", _T
    )
    topic, record = events[0]
    assert topic == persistence.SUBMISSIONS_TOPIC
    assert record["request_id"] == "req2"
    assert record["session_id"] == "sess-2"
    assert record["user_id"] == "u1"
    assert record["selected_career"] is None
    assert record["created_at"] == _T  # handler-minted, passed through untouched


def test_save_selection_carries_click_time(monkeypatch):
    monkeypatch.setattr(persistence, "enabled", lambda: True)
    events = []
    monkeypatch.setattr(persistence, "publish", lambda topic, data: events.append((topic, data)))
    persistence.save_selection("sess-2", "frontend", _T)
    topic, payload = events[0]
    assert topic == persistence.SELECTIONS_TOPIC
    assert payload == {"session_id": "sess-2", "career_id": "frontend", "selected_at": _T}


def test_save_functions_swallow_publish_errors(monkeypatch):
    monkeypatch.setattr(persistence, "enabled", lambda: True)

    def _boom(topic, data):
        raise DaprError("sidecar down")

    monkeypatch.setattr(persistence, "publish", _boom)
    # Should log and return, not propagate.
    persistence.save_submission("req3", {"q1": 1}, [{"id": "frontend"}], None, None, _T)
    persistence.save_selection("sess3", "frontend", _T)


def test_submit_calls_persistence(client_with_repo, valid_answers, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_submission",
        lambda request_id, answers, recs, session_id, user_id, created_at: calls.append(
            (request_id, answers, recs, session_id, created_at)
        ),
    )

    r = client_with_repo.post(
        "/api/questionnaire/submit",
        json={"answers": valid_answers, "session_id": "sess-xyz"},
    )
    assert r.status_code == 200

    assert len(calls) == 1
    request_id, answers, recs, session_id, created_at = calls[0]
    assert request_id == r.json()["request_id"]
    assert answers == valid_answers
    assert session_id == "sess-xyz"
    assert isinstance(recs, list) and all(isinstance(rec, dict) for rec in recs)
    assert created_at  # minted in the handler, not the background task


def test_select_calls_persistence(client_with_repo, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_selection",
        lambda session_id, career_id, selected_at: calls.append(
            (session_id, career_id, bool(selected_at))
        ),
    )

    r = client_with_repo.post(
        "/api/questionnaire/select",
        json={"session_id": "sess-xyz", "career_id": "frontend"},
    )
    assert r.status_code == 200
    assert calls == [("sess-xyz", "frontend", True)]


def test_select_rejects_unknown_career(client_with_repo):
    r = client_with_repo.post(
        "/api/questionnaire/select",
        json={"session_id": "sess-xyz", "career_id": "astronaut"},
    )
    assert r.status_code == 422


def test_select_rejects_malformed_session_id(client_with_repo):
    # Session ids become state-store keys; URL-ish ones are rejected up front.
    r = client_with_repo.post(
        "/api/questionnaire/select",
        json={"session_id": "a/b?c#d", "career_id": "frontend"},
    )
    assert r.status_code == 422


def test_submit_drops_malformed_session_id(client_with_repo, valid_answers, monkeypatch):
    # Submit must never 422 over a bad session id — it's dropped, quiz proceeds.
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_submission",
        lambda request_id, answers, recs, session_id, user_id, created_at: calls.append(session_id),
    )
    r = client_with_repo.post(
        "/api/questionnaire/submit",
        json={"answers": valid_answers, "session_id": "a/b?c#d"},
    )
    assert r.status_code == 200
    assert calls == [None]
