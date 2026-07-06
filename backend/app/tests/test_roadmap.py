"""Roadmap endpoint: static GET, personalized POST, LLM with static fallback."""
from fastapi.testclient import TestClient

from app.main import app
from app.services import roadmap_service as svc
from app.services.requirements_service import FakeRequirementsService


def test_roadmap_returns_sections(client_no_repo):
    r = client_no_repo.get("/api/roadmap/frontend")
    assert r.status_code == 200
    sections = r.json()["sections"]
    assert isinstance(sections, list) and sections
    assert {"id", "label", "nodes"} <= set(sections[0])


def test_roadmap_unknown_career_404(client_no_repo):
    r = client_no_repo.get("/api/roadmap/not-a-career")
    assert r.status_code == 404


def test_post_roadmap_falls_back_to_static_without_openai(client_no_repo):
    # OPENAI_API_KEY is forced empty in tests -> personalized POST returns the static roadmap.
    r = client_no_repo.post(
        "/api/roadmap/frontend", json={"missing_skills": ["GraphQL", "Testing"]}
    )
    assert r.status_code == 200
    assert r.json()["sections"]  # same static shape


def test_get_roadmap_uses_llm_when_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.core.config import get_settings
    get_settings.cache_clear()
    generated = {"sections": [{"id": "s1", "label": "Phase 1", "nodes": [
        {"id": "n1", "label": "Thing", "level": "beginner", "type": "required",
         "description": "d", "resources": []}]}]}
    monkeypatch.setattr(svc, "_generate", lambda *a, **k: generated)
    out = svc.get_roadmap("frontend", missing_skills=["X"])
    assert out is generated


def test_get_roadmap_falls_back_when_llm_errors(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.core.config import get_settings
    get_settings.cache_clear()

    def _boom(*a, **k):
        raise RuntimeError("openai down")

    monkeypatch.setattr(svc, "_generate", _boom)
    out = svc.get_roadmap("frontend", missing_skills=["X"])
    assert out is not None and out["sections"]  # static fallback


def test_validate_normalizes_bad_level_and_type():
    data = {"sections": [{"id": "s", "label": "L", "nodes": [
        {"id": "n", "label": "N", "level": "wizard", "type": "mandatory"}]}]}
    out = svc._validate(data)
    node = out["sections"][0]["nodes"][0]
    assert node["level"] == "intermediate" and node["type"] == "required"
    assert node["resources"] == [] and node["description"] == ""


# --- DEV-59: job-ad requirement enrichment on the personalized POST -----------------

_FAKE_REQUIREMENTS = {
    "required": [{"skill": "React", "count": 31, "total": 50, "pct": 62}],
    "advantage": [{"skill": "GraphQL", "count": 9, "total": 50, "pct": 18}],
}


def test_post_roadmap_injects_required_and_advantage_columns():
    app.state.requirements = FakeRequirementsService(_FAKE_REQUIREMENTS)
    try:
        client = TestClient(app)
        r = client.post("/api/roadmap/frontend", json={"missing_skills": []})
        assert r.status_code == 200
        sections = {s["id"]: s for s in r.json()["sections"]}

        # Required and Advantage are now separate columns.
        assert sections["in-demand"]["source"] == "job_ads"
        req_nodes = {n["label"]: n for n in sections["in-demand"]["nodes"]}
        assert set(req_nodes) == {"React"}
        react = req_nodes["React"]
        assert react["type"] == "required"
        assert react["demand"] == {"classification": "required", "count": 31, "total": 50, "pct": 62}
        assert "62%" in react["description"]

        assert sections["advantage"]["source"] == "job_ads"
        adv_nodes = {n["label"]: n for n in sections["advantage"]["nodes"]}
        assert set(adv_nodes) == {"GraphQL"}
        gql = adv_nodes["GraphQL"]
        assert gql["type"] == "good-to-know"
        assert gql["demand"]["classification"] == "advantage"
    finally:
        app.state.requirements = None


def test_post_roadmap_injection_does_not_mutate_cached_roadmap():
    """The injected sections must appear exactly once even across repeated requests —
    guards against mutating load_roadmaps()'s shared @lru_cache object."""
    app.state.requirements = FakeRequirementsService(_FAKE_REQUIREMENTS)
    try:
        client = TestClient(app)
        first = client.post("/api/roadmap/frontend", json={"missing_skills": []}).json()
        second = client.post("/api/roadmap/frontend", json={"missing_skills": []}).json()
        for body in (first, second):
            ids = [s["id"] for s in body["sections"]]
            assert ids.count("in-demand") == 1
            assert ids.count("advantage") == 1
    finally:
        app.state.requirements = None


def test_post_roadmap_only_required_omits_advantage_column():
    app.state.requirements = FakeRequirementsService(
        {"required": [{"skill": "React", "count": 40, "total": 50, "pct": 80}], "advantage": []}
    )
    try:
        client = TestClient(app)
        ids = [s["id"] for s in client.post("/api/roadmap/frontend", json={"missing_skills": []}).json()["sections"]]
        assert "in-demand" in ids and "advantage" not in ids
    finally:
        app.state.requirements = None


def test_post_roadmap_no_requirements_service_leaves_roadmap_plain(client_no_repo):
    # No requirements source (RAG down / tests): plain roadmap, no injected columns.
    r = client_no_repo.post("/api/roadmap/frontend", json={"missing_skills": []})
    assert r.status_code == 200
    assert all(s["id"] not in ("in-demand", "advantage") for s in r.json()["sections"])


def test_inject_requirements_empty_returns_roadmap_unchanged():
    roadmap = {"sections": [{"id": "s", "label": "L", "nodes": []}]}
    same = svc.inject_requirements(roadmap, {"required": [], "advantage": []})
    assert same is roadmap  # nothing to add -> untouched
    assert svc.inject_requirements(roadmap, None) is roadmap
