def test_health_ok(client_no_repo):
    r = client_no_repo.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "career-discovery-api"
    # No repo -> offline fallback: RAG not ready and zero docs.
    assert body["rag_ready"] is False
    assert body["rag_doc_count"] == 0


def test_health_reports_rag_doc_count(client_with_repo):
    body = client_with_repo.get("/api/health").json()
    assert body["rag_ready"] is True
    # Fake repo surfaces its candidate count; must be a positive int.
    assert isinstance(body["rag_doc_count"], int)
    assert body["rag_doc_count"] > 0
