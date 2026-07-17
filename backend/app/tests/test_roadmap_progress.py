"""Roadmap progress routes: auth-gated GET/POST, Dapr-state-backed reads/writes.

Same strategy as test_auth.py: default (_backends_disabled) makes auth fail with
503; the happy path monkeypatches get_user_from_token + the state functions the
service imported by name (mirrors the old fake-Supabase-client pattern).
"""
from app.services import auth_service, roadmap_progress_service

_USER = lambda jwt: auth_service.UserResponse(  # noqa: E731
    user_id="user-uuid-123", email="user@example.com", username="testuser"
)


def _fake_state(monkeypatch, data: dict):
    """Enable Dapr for the service and back it with a plain dict."""
    monkeypatch.setattr(roadmap_progress_service, "enabled", lambda: True)
    monkeypatch.setattr(roadmap_progress_service, "get_state", lambda key: data.get(key))
    monkeypatch.setattr(
        roadmap_progress_service, "save_state", lambda key, value: data.__setitem__(key, value)
    )
    return data


# --- auth gating -----------------------------------------------------------

def test_get_progress_no_auth_401(client_with_repo):
    r = client_with_repo.get("/api/roadmap/frontend/progress")
    assert r.status_code == 401


def test_get_progress_dapr_disabled_503(client_with_repo, monkeypatch):
    # Authenticated, but the state store is off -> the progress service 503s.
    monkeypatch.setattr(auth_service, "get_user_from_token", _USER)
    r = client_with_repo.get(
        "/api/roadmap/frontend/progress", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code == 503


def test_post_progress_no_auth_401(client_with_repo):
    r = client_with_repo.post(
        "/api/roadmap/frontend/progress", json={"completed_nodes": ["react"]}
    )
    assert r.status_code == 401


# --- happy path ------------------------------------------------------------

def test_get_progress_returns_completed_nodes(client_with_repo, monkeypatch):
    monkeypatch.setattr(auth_service, "get_user_from_token", _USER)
    _fake_state(
        monkeypatch,
        {
            "progress:user-uuid-123:frontend": {
                "completed_nodes": ["react", "typescript"],
                "updated_at": "2026-07-16T10:00:00+00:00",
            }
        },
    )
    r = client_with_repo.get(
        "/api/roadmap/frontend/progress", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == ["react", "typescript"]


def test_get_progress_empty_when_no_entry(client_with_repo, monkeypatch):
    monkeypatch.setattr(auth_service, "get_user_from_token", _USER)
    _fake_state(monkeypatch, {})
    r = client_with_repo.get(
        "/api/roadmap/frontend/progress", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == []


def test_post_progress_returns_saved_nodes(client_with_repo, monkeypatch):
    monkeypatch.setattr(auth_service, "get_user_from_token", _USER)
    data = _fake_state(monkeypatch, {})
    r = client_with_repo.post(
        "/api/roadmap/frontend/progress",
        json={"completed_nodes": ["react", "testing"]},
        headers={"Authorization": "Bearer t"},
    )
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == ["react", "testing"]
    saved = data["progress:user-uuid-123:frontend"]
    assert saved["completed_nodes"] == ["react", "testing"]
    assert saved["updated_at"]  # timestamp written alongside the nodes
