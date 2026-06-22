def test_health_ok(client_no_repo):
    r = client_no_repo.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "career-discovery-api"
