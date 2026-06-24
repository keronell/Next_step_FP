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

        def execute(self, *a, **k):
            raise RuntimeError("supabase down")

    monkeypatch.setattr(persistence, "_client", lambda: _Boom())
    # Should log and return, not propagate.
    persistence.save_submission("req2", {"q1": 1}, [{"id": "frontend"}])


def test_submit_schedules_persistence(client_with_repo, valid_answers, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_submission",
        lambda request_id, answers, recs: calls.append((request_id, answers, recs)),
    )

    r = client_with_repo.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 200

    # TestClient runs background tasks after the response.
    assert len(calls) == 1
    request_id, answers, recs = calls[0]
    assert request_id == r.json()["request_id"]
    assert answers == valid_answers
    assert isinstance(recs, list) and all(isinstance(rec, dict) for rec in recs)
