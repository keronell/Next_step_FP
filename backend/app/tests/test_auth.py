"""Auth route and service tests.

Strategy:
- Default autouse fixture (_supabase_disabled) sets SUPABASE_URL="" so all
  auth routes return 503 by default — tests the "unavailable" contract.
- Tests that need an "enabled" Supabase monkeypatch auth_service._get_auth_client
  to return a FakeClient — no real DB or network calls.
"""
import pytest
from fastapi import HTTPException, status

from app.services import auth_service


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

class _FakeUser:
    id = "user-uuid-123"
    email = "user@example.com"


class _FakeSession:
    access_token = "fake-access-token"
    refresh_token = "fake-refresh-token"


class _FakeAuthResponse:
    user = _FakeUser()
    session = _FakeSession()


class _FakeAdmin:
    def create_user(self, attrs):
        return _FakeAuthResponse()

    def sign_out(self, uid, scope="global"):
        pass


class _FakeGoTrue:
    admin = _FakeAdmin()

    def get_user(self, jwt):
        return _FakeAuthResponse()

    def sign_in_with_password(self, creds):
        return _FakeAuthResponse()


class _FakeTableResult:
    data = []


class _FakeTableBuilder:
    def select(self, *a, **k):
        return self
    def eq(self, *a, **k):
        return self
    def ilike(self, *a, **k):
        return self
    def is_(self, *a, **k):
        return self
    def order(self, *a, **k):
        return self
    def limit(self, *a, **k):
        return self
    def update(self, *a, **k):
        return self
    def insert(self, *a, **k):
        return self
    def execute(self):
        return _FakeTableResult()


class _FakeClient:
    auth = _FakeGoTrue()

    def table(self, name):
        return _FakeTableBuilder()


@pytest.fixture
def auth_client(monkeypatch):
    """Replace _get_auth_client with one that returns FakeClient."""
    fake = _FakeClient()
    monkeypatch.setattr(auth_service, "_get_auth_client", lambda: fake)
    return fake


# ---------------------------------------------------------------------------
# Auth unavailable (default: Supabase disabled)
# ---------------------------------------------------------------------------

def test_register_when_disabled(client_with_repo):
    r = client_with_repo.post(
        "/api/auth/register",
        json={"email": "a@b.com", "password": "password123", "username": "testuser"},
    )
    assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_login_when_disabled(client_with_repo):
    r = client_with_repo.post(
        "/api/auth/login", json={"email": "a@b.com", "password": "password123"}
    )
    assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_me_no_auth_header(client_with_repo):
    r = client_with_repo.get("/api/auth/me")
    assert r.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_invalid_token_raises_401(client_with_repo, monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: (_ for _ in ()).throw(
            HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")
        ),
    )
    r = client_with_repo.get(
        "/api/auth/me", headers={"Authorization": "Bearer bad-token"}
    )
    assert r.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_when_disabled(client_with_repo, monkeypatch):
    # Even with a "valid" token, logout must 503 when Supabase is off because
    # get_current_user calls get_user_from_token which calls _get_auth_client.
    r = client_with_repo.post(
        "/api/auth/logout", headers={"Authorization": "Bearer some-token"}
    )
    assert r.status_code in (
        status.HTTP_401_UNAUTHORIZED,  # token verification fails first
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def test_claim_sessions_when_disabled(client_with_repo):
    r = client_with_repo.post(
        "/api/auth/claim-sessions",
        json={"session_id": "sess-abc"},
        headers={"Authorization": "Bearer some-token"},
    )
    assert r.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


# ---------------------------------------------------------------------------
# Auth happy path (fake Supabase enabled)
# ---------------------------------------------------------------------------

def test_me_valid_token(client_with_repo, monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: auth_service.UserResponse(
            user_id="user-uuid-123", email="user@example.com", username="testuser"
        ),
    )
    r = client_with_repo.get(
        "/api/auth/me", headers={"Authorization": "Bearer valid-token"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "user-uuid-123"
    assert body["email"] == "user@example.com"
    assert body["username"] == "testuser"


def test_register_success(client_with_repo, auth_client):
    r = client_with_repo.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "securepass", "username": "newuser"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "fake-access-token"
    assert body["refresh_token"] == "fake-refresh-token"
    assert body["user_id"] == "user-uuid-123"
    assert body["email"] == "user@example.com"
    assert "username" in body


def test_login_success(client_with_repo, auth_client):
    r = client_with_repo.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "securepass"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "fake-access-token"


def test_logout_success(client_with_repo, monkeypatch, auth_client):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: auth_service.UserResponse(
            user_id="user-uuid-123", email="user@example.com", username="testuser"
        ),
    )
    r = client_with_repo.post(
        "/api/auth/logout", headers={"Authorization": "Bearer valid-token"}
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_claim_sessions_success(client_with_repo, monkeypatch, auth_client):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: auth_service.UserResponse(
            user_id="user-uuid-123", email="user@example.com", username="testuser"
        ),
    )
    r = client_with_repo.post(
        "/api/auth/claim-sessions",
        json={"session_id": "sess-abc"},
        headers={"Authorization": "Bearer valid-token"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_my_submissions_returns_list(client_with_repo, monkeypatch, auth_client):
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: auth_service.UserResponse(
            user_id="user-uuid-123", email="user@example.com", username="testuser"
        ),
    )
    r = client_with_repo.get(
        "/api/auth/my-submissions",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Questionnaire /submit with optional auth
# ---------------------------------------------------------------------------

def test_submit_with_auth_passes_user_id(client_with_repo, valid_answers, monkeypatch):
    """A logged-in user's submission includes their user_id in the persistence call."""
    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        lambda jwt: auth_service.UserResponse(
            user_id="user-uuid-123", email="user@example.com", username="testuser"
        ),
    )
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_submission",
        lambda request_id, answers, recs, session_id, user_id=None: calls.append(
            {"request_id": request_id, "user_id": user_id}
        ),
    )
    r = client_with_repo.post(
        "/api/questionnaire/submit",
        json={"answers": valid_answers, "session_id": "sess-xyz"},
        headers={"Authorization": "Bearer valid-token"},
    )
    assert r.status_code == 200
    assert calls[0]["user_id"] == "user-uuid-123"


def test_submit_without_auth_passes_null_user_id(
    client_with_repo, valid_answers, monkeypatch
):
    """Anonymous submission still works; user_id is None in the persistence call."""
    calls = []
    monkeypatch.setattr(
        "app.api.routes.questionnaire.save_submission",
        lambda request_id, answers, recs, session_id, user_id=None: calls.append(
            {"request_id": request_id, "user_id": user_id}
        ),
    )
    r = client_with_repo.post(
        "/api/questionnaire/submit",
        json={"answers": valid_answers, "session_id": "sess-xyz"},
    )
    assert r.status_code == 200
    assert calls[0]["user_id"] is None


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_register_short_password_rejected(client_with_repo):
    r = client_with_repo.post(
        "/api/auth/register",
        json={"email": "a@b.com", "password": "short", "username": "testuser"},
    )
    assert r.status_code == 422


def test_register_invalid_email_rejected(client_with_repo):
    r = client_with_repo.post(
        "/api/auth/register",
        json={"email": "notanemail", "password": "password123", "username": "testuser"},
    )
    assert r.status_code == 422


def test_register_missing_username_rejected(client_with_repo):
    r = client_with_repo.post(
        "/api/auth/register", json={"email": "a@b.com", "password": "password123"}
    )
    assert r.status_code == 422


def test_register_invalid_username_rejected(client_with_repo):
    r = client_with_repo.post(
        "/api/auth/register",
        json={"email": "a@b.com", "password": "password123", "username": "bad user!"},
    )
    assert r.status_code == 422


def test_register_duplicate_username_rejected(client_with_repo, monkeypatch):
    """Username uniqueness check: 400 when a username is already taken."""
    class _TakenTableResult:
        data = [{"user_id": "existing-uuid"}]

    class _TakenTableBuilder(_FakeTableBuilder):
        def execute(self):
            return _TakenTableResult()

    class _TakenClient(_FakeClient):
        def table(self, name):
            return _TakenTableBuilder()

    monkeypatch.setattr(auth_service, "_get_auth_client", lambda: _TakenClient())
    r = client_with_repo.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "securepass", "username": "takenuser"},
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["detail"] == "Username already taken."
