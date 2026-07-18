"""GET /internal/verify — the token-verification contract every other service
depends on (common/auth_dep.py invokes this)."""
from fastapi import HTTPException, status

from app.services import auth_service


def test_verify_no_header_401(client):
    assert client.get("/internal/verify").status_code == 401


def test_verify_supabase_disabled_503(client):
    r = client.get("/internal/verify", headers={"Authorization": "Bearer t"})
    assert r.status_code == 503


def test_verify_invalid_token_401(client, monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: (_ for _ in ()).throw(
            HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")
        ),
    )
    r = client.get("/internal/verify", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 401


def test_verify_valid_token_returns_user(client, monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: auth_service.UserResponse(
            user_id="user-uuid-123", email="user@example.com", username="testuser"
        ),
    )
    r = client.get("/internal/verify", headers={"Authorization": "Bearer good"})
    assert r.status_code == 200
    assert r.json() == {
        "user_id": "user-uuid-123",
        "email": "user@example.com",
        "username": "testuser",
    }
