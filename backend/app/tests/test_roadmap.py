"""Roadmap endpoint: static GET, personalized POST, LLM with static fallback."""
from app.services import roadmap_service as svc


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
