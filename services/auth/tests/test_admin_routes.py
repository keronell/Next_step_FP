"""Admin route tests (DEV-62).

Strategy mirrors test_auth.py: the autouse fixture leaves Supabase off (so the
503 contract is the default), and tests that need it patch the client accessors
with fakes. The caller's role is injected by patching get_user_from_token —
the same seam every other auth test uses to stand in for a valid token.
"""
from datetime import datetime, timezone

import pytest
from fastapi import status

from app.services import auth_service
from common.models.auth import UserResponse

# Real uuid shape: the delete route constrains the path segment to one. Hex LETTERS
# on purpose — an all-numeric id is unchanged by .upper() and would hide the
# case-folding bug the self-delete guard has to defend against.
ADMIN_ID = "aaaaaaaa-1111-4111-8111-1111111111ab"
USER_ID = "bbbbbbbb-2222-4222-8222-2222222222cd"


def _as(user_id: str, role: str) -> UserResponse:
    return UserResponse(
        user_id=user_id, email=f"{role}@example.com", username=role, role=role
    )


@pytest.fixture
def signed_in(monkeypatch):
    """Make every Bearer token resolve to the given caller."""
    def _set(user: UserResponse):
        monkeypatch.setattr(auth_service, "get_user_from_token", lambda jwt: user)
    return _set


# ---------------------------------------------------------------------------
# Fake Supabase
# ---------------------------------------------------------------------------

class _GoTrueUser:
    def __init__(self, uid, email, created_at):
        self.id = uid
        self.email = email
        self.created_at = created_at


class _FakeAdminAPI:
    def __init__(self, users):
        self._users = users
        self.deleted = []

    def list_users(self, page=None, per_page=None):
        self.last_per_page = per_page
        return self._users

    def delete_user(self, uid):
        self.deleted.append(uid)


class _FakeTableResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        return _FakeTableResult(self._rows)


class _FakeClient:
    def __init__(self, users, rows):
        self.auth = type("_A", (), {"admin": _FakeAdminAPI(users)})()
        self._rows = rows

    def table(self, name):
        return _FakeTable(self._rows)


@pytest.fixture
def supabase(monkeypatch):
    """Two accounts in GoTrue; only one of them has a user_profiles row."""
    fake = _FakeClient(
        users=[
            _GoTrueUser(ADMIN_ID, "admin@example.com",
                        datetime(2026, 1, 2, tzinfo=timezone.utc)),
            _GoTrueUser(USER_ID, "user@example.com",
                        datetime(2026, 3, 4, tzinfo=timezone.utc)),
        ],
        rows=[{"user_id": ADMIN_ID, "username": "ronen", "role": "admin"}],
    )
    monkeypatch.setattr(auth_service, "_get_admin_client", lambda: fake)
    monkeypatch.setattr(auth_service, "_get_data_client", lambda: fake)
    return fake


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def test_list_requires_a_token(client):
    assert client.get("/api/admin/users").status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_requires_a_token(client):
    r = client.delete(f"/api/admin/users/{USER_ID}")
    assert r.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_forbidden_for_normal_user(client, signed_in, supabase):
    signed_in(_as(USER_ID, "user"))
    r = client.get("/api/admin/users", headers={"Authorization": "Bearer t"})
    assert r.status_code == status.HTTP_403_FORBIDDEN


def test_delete_forbidden_for_normal_user(client, signed_in, supabase):
    signed_in(_as(USER_ID, "user"))
    r = client.delete(f"/api/admin/users/{ADMIN_ID}", headers={"Authorization": "Bearer t"})
    assert r.status_code == status.HTTP_403_FORBIDDEN
    assert supabase.auth.admin.deleted == []


def test_list_503_when_supabase_disabled(client, signed_in):
    """An admin caller still gets 503, not 500, when Supabase is unconfigured."""
    signed_in(_as(ADMIN_ID, "admin"))
    r = client.get("/api/admin/users", headers={"Authorization": "Bearer t"})
    assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def test_list_merges_gotrue_and_profiles(client, signed_in, supabase):
    signed_in(_as(ADMIN_ID, "admin"))
    r = client.get("/api/admin/users", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    body = r.json()
    assert [u["user_id"] for u in body] == [USER_ID, ADMIN_ID]  # newest first

    admin_row = body[1]
    assert admin_row["email"] == "admin@example.com"
    assert admin_row["username"] == "ronen"
    assert admin_row["role"] == "admin"

    # An account with no user_profiles row still lists, as a plain user.
    orphan = body[0]
    assert orphan["email"] == "user@example.com"
    assert orphan["username"] == ""
    assert orphan["role"] == "user"


def test_list_is_capped(client, signed_in, supabase):
    signed_in(_as(ADMIN_ID, "admin"))
    client.get("/api/admin/users", headers={"Authorization": "Bearer t"})
    assert supabase.auth.admin.last_per_page == auth_service.ADMIN_LIST_LIMIT


# ---------------------------------------------------------------------------
# Deleting
# ---------------------------------------------------------------------------

def test_admin_deletes_another_account(client, signed_in, supabase):
    signed_in(_as(ADMIN_ID, "admin"))
    r = client.delete(f"/api/admin/users/{USER_ID}", headers={"Authorization": "Bearer t"})
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert supabase.auth.admin.deleted == [USER_ID]


def test_admin_cannot_delete_self(client, signed_in, supabase):
    signed_in(_as(ADMIN_ID, "admin"))
    r = client.delete(f"/api/admin/users/{ADMIN_ID}", headers={"Authorization": "Bearer t"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert supabase.auth.admin.deleted == []


def test_admin_cannot_delete_self_in_a_different_case(client, signed_in, supabase):
    """Postgres parses uuids case-insensitively, so an uppercased copy of your own
    id still addresses your own account — the guard must not compare byte-exact."""
    signed_in(_as(ADMIN_ID, "admin"))
    r = client.delete(
        f"/api/admin/users/{ADMIN_ID.upper()}", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert supabase.auth.admin.deleted == []


def test_delete_rejects_a_malformed_id(client, signed_in, supabase):
    """The id is interpolated into a GoTrue admin URL — keep the charset tight."""
    signed_in(_as(ADMIN_ID, "admin"))
    r = client.delete("/api/admin/users/..%2Fsettings", headers={"Authorization": "Bearer t"})
    assert r.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY)
    assert supabase.auth.admin.deleted == []


# ---------------------------------------------------------------------------
# Role plumbing
# ---------------------------------------------------------------------------

def test_fetch_profile_defaults_when_no_row(monkeypatch):
    monkeypatch.setattr(auth_service, "_get_data_client", lambda: _FakeClient([], []))
    assert auth_service._fetch_profile("nobody") == ("", "user")


def test_fetch_profile_reads_role(monkeypatch, supabase):
    assert auth_service._fetch_profile(ADMIN_ID) == ("ronen", "admin")


def test_me_carries_the_role(client, signed_in, supabase):
    signed_in(_as(ADMIN_ID, "admin"))
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
