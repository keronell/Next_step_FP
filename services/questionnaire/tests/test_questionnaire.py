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
    """Records (answers, profile) per call — the profile is the DEV-60 self-input."""
    calls = []
    monkeypatch.setattr(
        q_routes,
        "match_remote",
        lambda answers, profile=None: calls.append((answers, profile)) or CANNED_RECS,
    )
    return calls


@pytest.fixture
def persisted(monkeypatch):
    calls = []
    monkeypatch.setattr(
        q_routes,
        "save_submission",
        lambda request_id, answers, recs, session_id, user_id, created_at, profile=None: calls.append(
            {"request_id": request_id, "session_id": session_id,
             "user_id": user_id, "created_at": created_at, "recs": recs,
             "profile": profile}
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
    assert matching_ok == [(valid_answers, None)]  # profile omitted -> skipped step
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
    monkeypatch.setattr(q_routes, "match_remote", lambda answers, profile=None: model_recs)
    r = client.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 200
    assert r.json()["model_caveats"] == ["warning one", "warning two"]


def test_the_real_artifacts_caveats_survive_the_response_and_reach_persistence(
    client, valid_answers, persisted, monkeypatch
):
    """DEV-99: the test above proves the derivation with hand-written strings. This one
    uses the REAL artifact's caveats, which is what a flip would actually carry.

    It closes the one hop matching-service's own end-to-end test cannot reach: that
    suite stops at /internal/match, and this service is where the response-level field
    is derived and where the persisted record is handed off. The caveats are prose with
    punctuation and a non-ASCII character, so "it is a list of strings" is not the same
    assurance as "these exact strings arrive".

    Reads the artifact rather than importing matching-service's loader — the two
    services do not share a venv or a package path, and the JSON is the contract.
    """
    import json
    from pathlib import Path

    artifact = Path(__file__).resolve().parents[3] / "data" / "models" / "matcher_nn_v1.json"
    if not artifact.exists():
        pytest.skip("matcher_nn_v1.json not present - run data/scripts/export_nn_model.py")
    caveats = json.loads(artifact.read_text(encoding="utf-8"))["caveats"]
    assert caveats, "the shipped artifact carries no caveats to propagate"

    model_recs = [dict(CANNED_RECS[0], model_version="matcher-nn-v1", model_caveats=caveats)]
    monkeypatch.setattr(q_routes, "match_remote", lambda answers, profile=None: model_recs)

    r = client.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 200
    assert r.json()["model_caveats"] == caveats
    # Named, not merely non-empty: the ADR 0002 mitigation caveat is the one whose loss
    # would leave an uncalibrated model looking calibrated all the way to the UI.
    assert any("NOT calibrated" in c for c in r.json()["model_caveats"])
    # And the same strings are what persistence is handed, per-rec.
    assert persisted[0]["recs"][0]["model_caveats"] == caveats
    assert persisted[0]["recs"][0]["model_version"] == "matcher-nn-v1"


def test_submit_forwards_the_self_input_profile_to_matching(
    client, valid_answers, matching_ok, persisted
):
    """DEV-60: the profile must actually reach matching-service, not just validate."""
    profile = {
        "skills": ["Python", "SQL"],
        "experience": [{"role": "Data Analyst", "duration_months": 24}],
        "projects": [{"name": "Dashboard", "technologies": ["Tableau"]}],
    }
    r = client.post(
        "/api/questionnaire/submit", json={"answers": valid_answers, "profile": profile}
    )
    assert r.status_code == 200
    _, forwarded = matching_ok[0]
    assert forwarded is not None
    assert forwarded.skills == ["Python", "SQL"]
    assert forwarded.experience[0].role == "Data Analyst"
    assert forwarded.projects[0].technologies == ["Tableau"]

    # Snapshotted with the submission: the live profile row is mutable, so without
    # this an edited profile leaves past recommendations unexplainable.
    assert persisted[0]["profile"]["skills"] == ["Python", "SQL"]


def test_submit_persists_no_profile_when_the_step_was_skipped(
    client, valid_answers, matching_ok, persisted
):
    client.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert persisted[0]["profile"] is None


def test_submit_response_keeps_the_user_skill_match_component(
    client, valid_answers, persisted, monkeypatch
):
    """The public response model revalidates matching's raw dicts, so a component
    it doesn't declare is silently dropped before the browser ever sees it."""
    profile_recs = [
        dict(
            CANNED_RECS[0],
            model_version="formula-v1+profile",
            score_breakdown={
                "semantic_similarity": 0.5,
                "questionnaire_fit": 1.0,
                "skill_overlap": 0.8,
                "user_skill_match": 0.94,
            },
        )
    ]
    monkeypatch.setattr(q_routes, "match_remote", lambda answers, profile=None: profile_recs)
    r = client.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 200
    assert r.json()["recommendations"][0]["score_breakdown"]["user_skill_match"] == 0.94


def test_submit_response_omits_user_skill_match_without_a_profile(
    client, valid_answers, matching_ok, persisted
):
    r = client.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.json()["recommendations"][0]["score_breakdown"]["user_skill_match"] is None


def test_submit_rejects_an_oversized_profile(client, valid_answers, matching_ok):
    """Trust boundary: submit is reachable unauthenticated, so caps are enforced."""
    r = client.post(
        "/api/questionnaire/submit",
        json={
            "answers": valid_answers,
            "profile": {"projects": [{"name": f"p{i}"} for i in range(11)]},
        },
    )
    assert r.status_code == 422
    assert matching_ok == []


def test_submit_propagates_matching_unavailable_503(client, valid_answers, monkeypatch):
    def _down(answers, profile=None):
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
