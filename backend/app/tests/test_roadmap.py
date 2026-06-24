"""The roadmap endpoint serves static career roadmaps; unknown ids 404."""


def test_roadmap_returns_sections(client_no_repo):
    r = client_no_repo.get("/api/roadmap/frontend")
    assert r.status_code == 200
    sections = r.json()["sections"]
    assert isinstance(sections, list) and sections
    assert {"id", "label", "nodes"} <= set(sections[0])


def test_roadmap_unknown_career_404(client_no_repo):
    r = client_no_repo.get("/api/roadmap/not-a-career")
    assert r.status_code == 404
