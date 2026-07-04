"""GET /api/questions — serves the authoritative question bank."""


def test_questions_returns_full_bank(client_no_repo):
    resp = client_no_repo.get("/api/questions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 10
    for q in data:
        assert {"id", "category", "text", "options"} <= set(q)
        assert isinstance(q["options"], list) and q["options"]


def test_questions_adaptive_show_if(client_no_repo):
    by_id = {q["id"]: q for q in client_no_repo.get("/api/questions").json()}
    assert by_id["q3"]["show_if"] == {"q": "q2", "in": [1, 2]}
    assert by_id["q9"]["show_if"] == {"q": "q2", "in": [0, 1]}
    # show_if may only reference earlier questions (keeps quiz indices stable)
    order = list(by_id)
    for qid, q in by_id.items():
        if "show_if" in q:
            assert order.index(q["show_if"]["q"]) < order.index(qid)
