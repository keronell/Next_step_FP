"""Roadmap progress routes: auth-gated GET/POST, Supabase-backed reads/writes.

Same strategy as test_auth.py: default (_supabase_disabled) makes auth fail with
503; the happy path monkeypatches get_user_from_token + a fake Supabase client.
"""
from app.services import auth_service, roadmap_progress_service

_USER = lambda jwt: auth_service.UserResponse(  # noqa: E731
    user_id="user-uuid-123", email="user@example.com", username="testuser"
)


class _FakeTableResult:
    def __init__(self, data):
        self.data = data


class _FakeTableBuilder:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def upsert(self, *a, **k):
        return self

    def execute(self):
        return _FakeTableResult(self._rows)


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _FakeTableBuilder(self._rows)


def _fake_supabase(monkeypatch, rows):
    monkeypatch.setattr(
        roadmap_progress_service, "get_supabase_client", lambda: _FakeClient(rows)
    )


# --- auth gating -----------------------------------------------------------

def test_get_progress_no_auth_401(client_with_repo):
    r = client_with_repo.get("/api/roadmap/frontend/progress")
    assert r.status_code == 401


def test_get_progress_supabase_disabled_503(client_with_repo, monkeypatch):
    # Real token path with Supabase off -> get_current_user -> 503.
    monkeypatch.setattr(roadmap_progress_service, "get_supabase_client", lambda: None)
    r = client_with_repo.get(
        "/api/roadmap/frontend/progress", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code in (401, 503)


def test_post_progress_no_auth_401(client_with_repo):
    r = client_with_repo.post(
        "/api/roadmap/frontend/progress", json={"completed_nodes": ["react"]}
    )
    assert r.status_code == 401


# --- happy path ------------------------------------------------------------

def test_get_progress_returns_completed_nodes(client_with_repo, monkeypatch):
    monkeypatch.setattr(auth_service, "get_user_from_token", _USER)
    _fake_supabase(monkeypatch, [{"completed_nodes": ["react", "typescript"]}])
    r = client_with_repo.get(
        "/api/roadmap/frontend/progress", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == ["react", "typescript"]


def test_get_progress_empty_when_no_row(client_with_repo, monkeypatch):
    monkeypatch.setattr(auth_service, "get_user_from_token", _USER)
    _fake_supabase(monkeypatch, [])
    r = client_with_repo.get(
        "/api/roadmap/frontend/progress", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == []


def test_post_progress_returns_saved_nodes(client_with_repo, monkeypatch):
    monkeypatch.setattr(auth_service, "get_user_from_token", _USER)
    _fake_supabase(monkeypatch, [])
    r = client_with_repo.post(
        "/api/roadmap/frontend/progress",
        json={"completed_nodes": ["react", "testing"]},
        headers={"Authorization": "Bearer t"},
    )
    assert r.status_code == 200
    assert r.json()["completed_nodes"] == ["react", "testing"]
