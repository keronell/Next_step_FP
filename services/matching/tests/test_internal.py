"""/internal/match + /internal/field-skills — the invocation surface other
services depend on. Ports the monolith's submit-quality assertions here (the
matching math now answers on this endpoint, not on /submit)."""
from collections import Counter

from fastapi.testclient import TestClient


def test_match_returns_sorted_recommendations(client_with_repo, valid_answers):
    r = client_with_repo.post("/internal/match", json={"answers": valid_answers})
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert 1 <= len(recs) <= 3
    scores = [rec["score"] for rec in recs]
    assert scores == sorted(scores, reverse=True)
    ids = [rec["id"] for rec in recs]
    assert len(ids) == len(set(ids))


def test_match_scores_in_unit_range_with_breakdown(client_with_repo, valid_answers):
    recs = client_with_repo.post("/internal/match", json={"answers": valid_answers}).json()[
        "recommendations"
    ]
    for rec in recs:
        assert 0.0 <= rec["score"] <= 1.0
        assert 0 <= rec["matchPercent"] <= 100
        for component in rec["score_breakdown"].values():
            assert 0.0 <= component <= 1.0
        assert 2 <= len(rec["reasons"]) <= 4
        for key in ("id", "title", "description", "keySkills", "icon", "roadmapKey"):
            assert key in rec


def test_match_rag_unavailable_returns_safe_503(client_no_repo, valid_answers):
    r = client_no_repo.post("/internal/match", json={"answers": valid_answers})
    assert r.status_code == 503
    assert r.json() == {"detail": "Career recommendations could not be generated at this time."}


class _FakeRag:
    def field_skills(self, field, sample_size):
        assert field == "software-development"
        assert sample_size == 50
        return Counter({"python": 30, "sql": 12}), 40


def test_field_skills_returns_counts(client_with_repo):
    from app.main import app

    app.state.rag = _FakeRag()
    try:
        r = client_with_repo.get("/internal/field-skills?field=software-development&sample_size=50")
        assert r.status_code == 200
        assert r.json() == {"counts": {"python": 30, "sql": 12}, "n_ads": 40}
    finally:
        app.state.rag = None


def test_field_skills_503_without_rag(client_no_repo):
    from app.main import app

    app.state.rag = None
    r = client_no_repo.get("/internal/field-skills?field=software-development")
    assert r.status_code == 503


def test_field_skills_sample_size_validated(client_with_repo):
    r = client_with_repo.get("/internal/field-skills?field=x&sample_size=0")
    assert r.status_code == 422
