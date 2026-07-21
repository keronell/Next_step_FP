"""my-submissions + claim-sessions routes: auth via the _verify seam, store via
module monkeypatching — contracts identical to the monolith versions."""
from app.routes import history as history_routes
from app.services import submission_store


def test_my_submissions_requires_auth(client):
    assert client.get("/api/auth/my-submissions").status_code in (401, 503)


def test_my_submissions_dapr_disabled_503(client, as_user):
    r = client.get("/api/auth/my-submissions", headers=as_user)
    assert r.status_code == 503


def test_my_submissions_returns_history(client, as_user, monkeypatch):
    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    monkeypatch.setattr(
        submission_store,
        "get_user_submissions",
        lambda user_id: [
            {
                "request_id": "r1",
                "recommendations": [{"id": "frontend"}],
                "selected_career": "frontend",
                "created_at": "2026-07-17T10:00:00+00:00",
            }
        ],
    )
    r = client.get("/api/auth/my-submissions", headers=as_user)
    assert r.status_code == 200
    body = r.json()
    assert body[0]["request_id"] == "r1"
    assert body[0]["selected_career"] == "frontend"


def test_my_submissions_store_error_500(client, as_user, monkeypatch):
    from common.dapr import DaprError

    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    monkeypatch.setattr(
        submission_store,
        "get_user_submissions",
        lambda user_id: (_ for _ in ()).throw(DaprError("store down")),
    )
    r = client.get("/api/auth/my-submissions", headers=as_user)
    assert r.status_code == 500


def test_claim_sessions_success(client, as_user, monkeypatch):
    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    calls = []
    monkeypatch.setattr(
        submission_store,
        "claim_sessions",
        lambda user_id, session_id: calls.append((user_id, session_id)) or 1,
    )
    r = client.post(
        "/api/auth/claim-sessions", json={"session_id": "sess-abc"}, headers=as_user
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert calls == [("user-uuid-123", "sess-abc")]


def test_claim_sessions_swallows_store_errors(client, as_user, monkeypatch):
    from common.dapr import DaprError

    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    monkeypatch.setattr(
        submission_store,
        "claim_sessions",
        lambda *a: (_ for _ in ()).throw(DaprError("store down")),
    )
    r = client.post(
        "/api/auth/claim-sessions", json={"session_id": "sess-abc"}, headers=as_user
    )
    assert r.status_code == 200  # best-effort past the gate — never breaks login


def test_claim_sessions_rejects_malformed_session_id(client, as_user):
    r = client.post(
        "/api/auth/claim-sessions", json={"session_id": "a/b?c#d"}, headers=as_user
    )
    assert r.status_code == 422


# ── DELETE /api/auth/my-submissions/{request_id} (DEV-75) ──────────────────────

def test_delete_submission_requires_auth(client):
    assert client.delete("/api/auth/my-submissions/abc123").status_code in (401, 503)


def test_delete_submission_dapr_disabled_503(client, as_user):
    assert client.delete("/api/auth/my-submissions/abc123", headers=as_user).status_code == 503


def test_delete_submission_success_204(client, as_user, monkeypatch):
    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    calls = []
    monkeypatch.setattr(
        submission_store,
        "delete_submission",
        lambda user_id, request_id: calls.append((user_id, request_id)) or True,
    )
    r = client.delete("/api/auth/my-submissions/abc123", headers=as_user)
    assert r.status_code == 204
    assert r.content == b""
    # Ownership is scoped to the authenticated user, passed through to the store.
    assert calls == [("user-uuid-123", "abc123")]


def test_delete_submission_not_found_or_not_owned_404(client, as_user, monkeypatch):
    # Store returns False for both "missing" and "belongs to another user" — the
    # route maps both to 404 so a user can't even probe others' submissions.
    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    monkeypatch.setattr(submission_store, "delete_submission", lambda *a: False)
    r = client.delete("/api/auth/my-submissions/abc123", headers=as_user)
    assert r.status_code == 404


def test_delete_submission_rejects_malformed_request_id(client, as_user, monkeypatch):
    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    # Path traversal / odd chars never reach the store.
    r = client.delete("/api/auth/my-submissions/a%2Fb", headers=as_user)
    assert r.status_code in (404, 422)


def test_delete_submission_store_error_500(client, as_user, monkeypatch):
    from common.dapr import DaprError

    monkeypatch.setattr(history_routes, "_require_dapr", lambda: None)
    monkeypatch.setattr(
        submission_store,
        "delete_submission",
        lambda *a: (_ for _ in ()).throw(DaprError("store down")),
    )
    r = client.delete("/api/auth/my-submissions/abc123", headers=as_user)
    assert r.status_code == 500
