"""Roadmap progress routes: auth-gated GET/POST, Dapr-state-backed reads/writes.

Auth is faked at the common.auth_dep._verify seam (as_user fixture); the state
functions the service imported by name are monkeypatched with a dict."""
from app.services import roadmap_progress_service


def _fake_state(monkeypatch, data: dict):
    """Enable Dapr for the service and back it with a plain dict."""
    monkeypatch.setattr(roadmap_progress_service, "enabled", lambda: True)
    monkeypatch.setattr(roadmap_progress_service, "get_state", lambda key: data.get(key))
    monkeypatch.setattr(
        roadmap_progress_service, "save_state", lambda key, value: data.__setitem__(key, value)
    )
    return data


# --- auth gating -----------------------------------------------------------

def test_get_progress_no_auth_401(client):
    r = client.get("/api/roadmap/frontend/progress")
    assert r.status_code == 401


def test_get_progress_dapr_disabled_503(client, as_user):
    # Authenticated, but the state store is off -> the progress service 503s.
    r = client.get("/api/roadmap/frontend/progress", headers=as_user)
    assert r.status_code == 503


def test_post_progress_no_auth_401(client):
    r = client.post("/api/roadmap/frontend/progress", json={"completed_nodes": ["react"]})
    assert r.status_code == 401


# --- happy path ------------------------------------------------------------

def test_get_progress_returns_completed_nodes(client, as_user, monkeypatch):
    _fake_state(
        monkeypatch,
        {
            "progress:user-uuid-123:frontend": {
                "completed_nodes": ["react", "typescript"],
                "updated_at": "2026-07-18T10:00:00+00:00",
            }
        },
    )
    r = client.get("/api/roadmap/frontend/progress", headers=as_user)
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == ["react", "typescript"]


def test_get_progress_empty_when_no_entry(client, as_user, monkeypatch):
    _fake_state(monkeypatch, {})
    r = client.get("/api/roadmap/frontend/progress", headers=as_user)
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == []


def test_post_progress_returns_saved_nodes(client, as_user, monkeypatch):
    data = _fake_state(monkeypatch, {})
    r = client.post(
        "/api/roadmap/frontend/progress",
        json={"completed_nodes": ["react", "testing"]},
        headers=as_user,
    )
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == ["react", "testing"]
    saved = data["progress:user-uuid-123:frontend"]
    assert saved["completed_nodes"] == ["react", "testing"]
    assert saved["updated_at"]
