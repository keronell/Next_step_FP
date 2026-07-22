"""Roadmap endpoint: static GET, personalized POST, LLM with static fallback."""
from fastapi.testclient import TestClient

from common.data import career_ids, load_roadmaps
from app.main import app
from app.services import roadmap_service as svc
from app.services.requirements_service import FakeRequirementsService

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


def test_roadmap_returns_sections(client):
    r = client.get("/api/roadmap/frontend")
    assert r.status_code == 200
    sections = r.json()["sections"]
    assert isinstance(sections, list) and sections
    assert {"id", "label", "nodes"} <= set(sections[0])


def test_roadmap_unknown_career_404(client):
    r = client.get("/api/roadmap/not-a-career")
    assert r.status_code == 404


def test_post_roadmap_falls_back_to_static_without_openai(client):
    # OPENAI_API_KEY is forced empty in tests -> personalized POST returns the static roadmap.
    r = client.post(
        "/api/roadmap/frontend", json={"missing_skills": ["GraphQL", "Testing"]}
    )
    assert r.status_code == 200
    assert r.json()["sections"]  # same static shape


def test_get_roadmap_uses_llm_when_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from common.config import get_settings
    get_settings.cache_clear()
    generated = {"sections": [{"id": "s1", "label": "Phase 1", "nodes": [
        {"id": "n1", "label": "Thing", "level": "beginner", "type": "required",
         "description": "d", "resources": []}]}]}
    monkeypatch.setattr(svc, "_generate", lambda *a, **k: generated)
    out = svc.get_roadmap("frontend", missing_skills=["X"])
    assert out is generated


def test_get_roadmap_falls_back_when_llm_errors(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from common.config import get_settings
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


def test_post_roadmap_no_requirements_service_leaves_roadmap_plain(client):
    # No requirements source (RAG down / tests): plain roadmap, no injected columns.
    r = client.post("/api/roadmap/frontend", json={"missing_skills": []})
    assert r.status_code == 200
    assert all(s["id"] not in ("in-demand", "advantage") for s in r.json()["sections"])


def test_inject_requirements_empty_returns_roadmap_unchanged():
    roadmap = {"sections": [{"id": "s", "label": "L", "nodes": []}]}
    same = svc.inject_requirements(roadmap, {"required": [], "advantage": []})
    assert same is roadmap  # nothing to add -> untouched
    assert svc.inject_requirements(roadmap, None) is roadmap


def test_slug_keeps_punctuation_skills_distinct():
    # "C#" and "C++" used to both slug to "c" (dropped # and +) -> duplicate node ids.
    assert svc._slug("C#") == "c-sharp"
    assert svc._slug("C++") == "c-plus-plus"
    assert svc._slug("C#") != svc._slug("C++")


def test_inject_requirements_ids_unique_across_columns():
    """Distinct skills must get distinct node ids (React keys / progress tracking).
    Covers both the C#/C++ encoding and the belt-and-suspenders uniqueness guard."""
    roadmap = {"sections": []}
    reqs = {
        "required": [
            {"skill": "C#", "count": 20, "total": 50, "pct": 40},
            {"skill": "C++", "count": 18, "total": 50, "pct": 36},
        ],
        # A contrived residual collision (both would slug to "market-c") is still
        # disambiguated by _unique_id, even across the required/advantage split.
        "advantage": [{"skill": "C", "count": 9, "total": 50, "pct": 18}],
    }
    out = svc.inject_requirements(roadmap, reqs)
    ids = [n["id"] for s in out["sections"] for n in s["nodes"]]
    assert ids == ["market-c-sharp", "market-c-plus-plus", "market-c"]
    assert len(ids) == len(set(ids))  # all distinct


# ── DEV-60: self-input profile reaches the generation prompt ───────────────────

PROFILE_DATA = {
    "experience": [
        {"role": "Data Analyst", "context": "a fintech", "duration_months": 24,
         "description": "built dashboards"}
    ],
    "projects": [],
    "skills": ["Python", "SQL"],
}


def test_profile_data_is_rendered_into_the_prompt(client, monkeypatch):
    """The frontend sends the profile structured; the route must render it with the
    SAME helper matching uses, so the two descriptions can never drift."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from common.config import get_settings
    get_settings.cache_clear()

    seen = {}
    monkeypatch.setattr(
        svc, "_generate",
        lambda career_id, profile, missing, settings, market=None: seen.update(profile=profile)
        or {"sections": [{"id": "s", "label": "L", "nodes": [
            {"id": "n", "label": "N", "level": "beginner", "type": "required",
             "description": "", "resources": []}]}]},
    )
    r = client.post("/api/roadmap/frontend", json={"profile_data": PROFILE_DATA})
    assert r.status_code == 200
    assert (
        "I worked as Data Analyst at a fintech for 2 years, where I built dashboards."
        in seen["profile"]
    )
    assert "I know python, sql." in seen["profile"]


def test_explicit_profile_string_wins_over_profile_data(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from common.config import get_settings
    get_settings.cache_clear()

    seen = {}
    monkeypatch.setattr(
        svc, "_generate",
        lambda career_id, profile, missing, settings, market=None: seen.update(profile=profile)
        or {"sections": [{"id": "s", "label": "L", "nodes": [
            {"id": "n", "label": "N", "level": "beginner", "type": "required",
             "description": "", "resources": []}]}]},
    )
    client.post(
        "/api/roadmap/frontend",
        json={"profile": "preset text", "profile_data": PROFILE_DATA},
    )
    assert seen["profile"] == "preset text"


def test_no_profile_data_leaves_the_prompt_profile_empty(client):
    """Static fallback path: absent profile must not become an empty-string prompt."""
    from app.routes.roadmap import RoadmapContext
    assert RoadmapContext().profile_text() is None
    assert RoadmapContext(profile_data={}).profile_text() is None
