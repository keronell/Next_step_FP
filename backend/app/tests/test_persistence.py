"""Persistence is best-effort: disabled => no-op, errors => swallowed, route still 200."""
from app.services import persistence


def test_save_submission_noop_when_disabled():
    # Default test settings have no Supabase creds => client is None => no-op, no raise.
    persistence._client.cache_clear()
    assert persistence._client() is None
    persistence.save_submission("req1", {"q1": 1}, [{"id": "frontend"}])  # must not raise


def test_save_submission_swallows_client_errors(monkeypatch):
    class _Boom:
        def table(self, *a, **k):
            return self

        def insert(self, *a, **k):
            return self

        def update(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def execute(self, *a, **k):
            raise RuntimeError("supabase down")

    monkeypatch.setattr(persistence, "_client", lambda: _Boom())
    # Should log and return, not propagate.
    persistence.save_submission("req2", {"q1": 1}, [{"id": "frontend"}])
    persistence.save_selection("sess2", "frontend")  # must not raise either


def test_save_selection_noop_when_disabled():
    persistence._client.cache_clear()
    assert persistence._client() is None
    persistence.save_selection("sess1", "frontend")  # no creds => no-op, no raise


def test_submit_schedules_persistence(client_with_repo, valid_answers, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_submission",
        lambda request_id, answers, recs, session_id, user_id=None: calls.append(
            (request_id, answers, recs, session_id)
        ),
    )

    r = client_with_repo.post(
        "/api/questionnaire/submit",
        json={"answers": valid_answers, "session_id": "sess-xyz"},
    )
    assert r.status_code == 200

    # TestClient runs background tasks after the response.
    assert len(calls) == 1
    request_id, answers, recs, session_id = calls[0]
    assert request_id == r.json()["request_id"]
    assert answers == valid_answers
    assert session_id == "sess-xyz"
    assert isinstance(recs, list) and all(isinstance(rec, dict) for rec in recs)


def test_select_schedules_persistence(client_with_repo, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_selection",
        lambda session_id, career_id: calls.append((session_id, career_id)),
    )

    r = client_with_repo.post(
        "/api/questionnaire/select",
        json={"session_id": "sess-xyz", "career_id": "frontend"},
    )
    assert r.status_code == 200
    assert calls == [("sess-xyz", "frontend")]


def test_select_rejects_unknown_career(client_with_repo):
    r = client_with_repo.post(
        "/api/questionnaire/select",
        json={"session_id": "sess-xyz", "career_id": "astronaut"},
    )
    assert r.status_code == 422
