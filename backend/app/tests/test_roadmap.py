"""Roadmap endpoint: static GET, personalized POST, LLM with static fallback."""
from app.data import career_ids, load_roadmaps
from app.services import roadmap_service as svc

_LEVELS = {"beginner", "intermediate", "advanced"}
_TYPES = {"required", "good-to-know", "optional"}


def test_every_career_has_a_wellformed_roadmap():
    """Every catalog career must resolve to a roadmap (no 404s), and each roadmap
    must satisfy the schema Roadmap.jsx renders: non-empty sections, unique node
    ids (they are progress keys), and legal level/type on every node."""
    roadmaps = load_roadmaps()
    for cid in career_ids():
        assert cid in roadmaps, f"career '{cid}' has no roadmap entry"
        sections = roadmaps[cid]["sections"]
        assert sections, cid
        node_ids = []
        for section in sections:
            assert section["id"] and section["label"] and section["nodes"], (cid, section.get("id"))
            for node in section["nodes"]:
                node_ids.append(node["id"])
                assert node["level"] in _LEVELS, (cid, node["id"], node["level"])
                assert node["type"] in _TYPES, (cid, node["id"], node["type"])
        assert len(node_ids) == len(set(node_ids)), f"{cid} has duplicate node ids"


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
