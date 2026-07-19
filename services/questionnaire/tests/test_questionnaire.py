"""Submit/select routes: validation parity with the monolith, plus the two new
seams — match_remote (invocation) and save_submission/save_selection (publish)."""
import pytest
from fastapi import HTTPException, status

from app.routes import questionnaire as q_routes
from common.auth_dep import SAFE_UNAVAILABLE

CANNED_RECS = [
    {
        "id": "frontend", "title": "Frontend Developer", "description": "d",
        "keySkills": ["react"], "icon": "Code", "roadmapKey": "frontend",
        "matchPercent": 88, "score": 0.88,
        "score_breakdown": {"semantic_similarity": 0.8, "questionnaire_fit": 0.9, "skill_overlap": 0.7},
        "reasons": ["r1", "r2"], "matched_skills": ["react"], "missing_skills": ["testing"],
        "model_version": "formula-v1",
    }
]


@pytest.fixture
def matching_ok(monkeypatch):
    calls = []
    monkeypatch.setattr(q_routes, "match_remote", lambda answers: calls.append(answers) or CANNED_RECS)
    return calls


@pytest.fixture
def persisted(monkeypatch):
    calls = []
    monkeypatch.setattr(
        q_routes,
        "save_submission",
        lambda request_id, answers, recs, session_id, user_id, created_at: calls.append(
            {"request_id": request_id, "session_id": session_id,
             "user_id": user_id, "created_at": created_at, "recs": recs}
        ),
    )
    return calls


def test_submit_returns_matching_result(client, valid_answers, matching_ok, persisted):
    r = client.post(
        "/api/questionnaire/submit", json={"answers": valid_answers, "session_id": "sess-1"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["recommendations"][0]["id"] == "frontend"
    assert body["model_caveats"] == []  # CANNED_RECS are formula-scored
    assert matching_ok == [valid_answers]
    assert len(persisted) == 1
    assert persisted[0]["request_id"] == body["request_id"]
    assert persisted[0]["session_id"] == "sess-1"
    assert persisted[0]["user_id"] is None  # anonymous (auth-service not consulted)
    assert persisted[0]["created_at"]  # minted in the handler


def test_submit_derives_response_caveats_from_model_scored_recs(
    client, valid_answers, persisted, monkeypatch
):
    """The response-level model_caveats field mirrors what matching-service embedded
    per recommendation — this service has no model object of its own."""
    model_recs = [dict(CANNED_RECS[0], model_version="matcher-logistic-v2",
                       model_caveats=["warning one", "warning two"])]
    monkeypatch.setattr(q_routes, "match_remote", lambda answers: model_recs)
    r = client.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 200
    assert r.json()["model_caveats"] == ["warning one", "warning two"]


def test_submit_propagates_matching_unavailable_503(client, valid_answers, monkeypatch):
    def _down(answers):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=SAFE_UNAVAILABLE)

    monkeypatch.setattr(q_routes, "match_remote", _down)
    r = client.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 503
    assert r.json() == {"detail": SAFE_UNAVAILABLE}


def test_submit_drops_malformed_session_id(client, valid_answers, matching_ok, persisted):
    r = client.post(
        "/api/questionnaire/submit", json={"answers": valid_answers, "session_id": "a/b?c#d"}
    )
    assert r.status_code == 200
    assert persisted[0]["session_id"] is None


# --- validation parity with the monolith (422 before any invocation) ---------

def test_empty_answers_rejected(client):
    assert client.post("/api/questionnaire/submit", json={"answers": {}}).status_code == 422


def test_all_null_answers_rejected(client):
    assert client.post("/api/questionnaire/submit", json={"answers": {"q1": None}}).status_code == 422


def test_out_of_range_value_rejected(client):
    assert client.post("/api/questionnaire/submit", json={"answers": {"q1": 9}}).status_code == 422


def test_unknown_question_rejected(client):
    assert client.post("/api/questionnaire/submit", json={"answers": {"qZ": 1}}).status_code == 422


# --- select ------------------------------------------------------------------

def test_select_publishes(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        q_routes,
        "save_selection",
        lambda session_id, career_id, selected_at: calls.append(
            (session_id, career_id, bool(selected_at))
        ),
    )
    r = client.post(
        "/api/questionnaire/select", json={"session_id": "sess-1", "career_id": "frontend"}
    )
    assert r.status_code == 200
    assert calls == [("sess-1", "frontend", True)]


def test_select_rejects_unknown_career(client):
    r = client.post(
        "/api/questionnaire/select", json={"session_id": "sess-1", "career_id": "astronaut"}
    )
    assert r.status_code == 422


def test_select_rejects_malformed_session_id(client):
    r = client.post(
        "/api/questionnaire/select", json={"session_id": "a/b?c#d", "career_id": "frontend"}
    )
    assert r.status_code == 422
