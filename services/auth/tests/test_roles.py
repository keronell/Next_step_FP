"""Role-based authorization (DEV-62).

Covers the four layers of the role model:
  1. pure helpers    — normalize_role / has_privilege privilege ordering
  2. extraction      — _role_from_user reading app_metadata safely
  3. default on signup — register() stamps app_metadata.role = "student"
  4. route gating    — require_role("admin") → 401/403/200 on /auth/admin/check
"""
import pytest
from fastapi import HTTPException, status

from app.services import auth_service
from common.models.auth import (
    DEFAULT_ROLE,
    UserResponse,
    has_privilege,
    normalize_role,
)


# ---------------------------------------------------------------------------
# 1. Pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("admin", "admin"),
        ("student", "student"),
        (None, "student"),          # missing claim (pre-DEV-62 accounts)
        ("", "student"),            # empty
        ("superuser", "student"),   # unknown role never elevates
        (123, "student"),           # wrong type
    ],
)
def test_normalize_role(value, expected):
    assert normalize_role(value) == expected


def test_default_role_is_least_privileged():
    assert DEFAULT_ROLE == "student"
    assert has_privilege("admin", "student")   # admin satisfies a student gate
    assert has_privilege("admin", "admin")
    assert has_privilege("student", "student")
    assert not has_privilege("student", "admin")  # student cannot reach admin
    assert not has_privilege("bogus", "student")  # unknown role has no privilege


# ---------------------------------------------------------------------------
# 2. Extraction from a GoTrue user object
# ---------------------------------------------------------------------------

class _UserWithRole:
    def __init__(self, app_metadata):
        self.app_metadata = app_metadata


def test_role_from_user_reads_app_metadata():
    assert auth_service._role_from_user(_UserWithRole({"role": "admin"})) == "admin"


def test_role_from_user_defaults_when_absent():
    assert auth_service._role_from_user(_UserWithRole({})) == "student"
    assert auth_service._role_from_user(_UserWithRole(None)) == "student"


def test_role_from_user_ignores_non_mapping_metadata():
    # A malformed app_metadata must not crash or elevate.
    assert auth_service._role_from_user(_UserWithRole("garbage")) == "student"


# ---------------------------------------------------------------------------
# 3. Default role assigned on signup
# ---------------------------------------------------------------------------

def test_register_stamps_default_role(client, monkeypatch):
    """create_user must be called with app_metadata.role == the default role."""
    captured = {}

    class _Admin:
        def create_user(self, attrs):
            captured.update(attrs)

            class _Resp:
                class user:
                    id = "new-uuid"
            return _Resp()

    class _TableBuilder:
        def select(self, *a, **k): return self
        def ilike(self, *a, **k): return self
        def insert(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def execute(self):
            class _Res:
                data = []
            return _Res()

    class _Client:
        class auth:
            admin = _Admin()

        def table(self, name):
            return _TableBuilder()

    fake = _Client()
    monkeypatch.setattr(auth_service, "_get_admin_client", lambda: fake)
    monkeypatch.setattr(auth_service, "_get_data_client", lambda: fake)
    # register() calls login() at the end; short-circuit it — we only care that
    # create_user received the right app_metadata.
    monkeypatch.setattr(
        auth_service,
        "login",
        lambda email, password: auth_service.AuthTokenResponse(
            access_token="a", refresh_token="r", user_id="new-uuid",
            email=email, username="newuser", role="student",
        ),
    )

    r = client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "password123", "username": "newuser"},
    )
    assert r.status_code == 200
    assert captured.get("app_metadata") == {"role": DEFAULT_ROLE}


# ---------------------------------------------------------------------------
# 4. Route gating: /api/auth/admin/check
# ---------------------------------------------------------------------------

def _patch_current_user(monkeypatch, role):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: UserResponse(
            user_id="u", email="u@example.com", username="u", role=role
        ),
    )


def test_admin_check_no_token_401(client):
    assert client.get("/api/auth/admin/check").status_code == 401


def test_admin_check_student_forbidden_403(client, monkeypatch):
    _patch_current_user(monkeypatch, "student")
    r = client.get("/api/auth/admin/check", headers={"Authorization": "Bearer t"})
    assert r.status_code == status.HTTP_403_FORBIDDEN


def test_admin_check_admin_allowed_200(client, monkeypatch):
    _patch_current_user(monkeypatch, "admin")
    r = client.get("/api/auth/admin/check", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_admin_check_invalid_token_401(client, monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: (_ for _ in ()).throw(
            HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad")
        ),
    )
    r = client.get("/api/auth/admin/check", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 401
