"""Route-level tests over the fake repository (full submit flow, no vector DB)."""


def test_valid_submission_returns_sorted_recommendations(client_with_repo, valid_answers):
    r = client_with_repo.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 200
    body = r.json()
    assert "request_id" in body
    recs = body["recommendations"]

    assert 1 <= len(recs) <= 3
    # Sorted descending by score.
    scores = [rec["score"] for rec in recs]
    assert scores == sorted(scores, reverse=True)
    # No duplicate careers.
    ids = [rec["id"] for rec in recs]
    assert len(ids) == len(set(ids))


def test_scores_in_unit_range_with_breakdown(client_with_repo, valid_answers):
    recs = client_with_repo.post(
        "/api/questionnaire/submit", json={"answers": valid_answers}
    ).json()["recommendations"]
    for rec in recs:
        assert 0.0 <= rec["score"] <= 1.0
        assert 0 <= rec["matchPercent"] <= 100
        for component in rec["score_breakdown"].values():
            assert 0.0 <= component <= 1.0
        assert 2 <= len(rec["reasons"]) <= 4
        # Shape the frontend renders is present.
        for key in ("id", "title", "description", "keySkills", "icon", "roadmapKey"):
            assert key in rec


def test_empty_answers_rejected(client_with_repo):
    r = client_with_repo.post("/api/questionnaire/submit", json={"answers": {}})
    assert r.status_code == 422


def test_all_null_answers_rejected(client_with_repo):
    r = client_with_repo.post("/api/questionnaire/submit", json={"answers": {"q1": None}})
    assert r.status_code == 422


def test_out_of_range_value_rejected(client_with_repo):
    r = client_with_repo.post("/api/questionnaire/submit", json={"answers": {"q1": 9}})
    assert r.status_code == 422


def test_unknown_question_rejected(client_with_repo):
    r = client_with_repo.post("/api/questionnaire/submit", json={"answers": {"qZ": 1}})
    assert r.status_code == 422


def test_rag_unavailable_returns_safe_503(client_no_repo, valid_answers):
    r = client_no_repo.post("/api/questionnaire/submit", json={"answers": valid_answers})
    assert r.status_code == 503
    assert r.json() == {"detail": "Career recommendations could not be generated at this time."}
