"""Auth operations wrapping Supabase GoTrue.

Unlike persistence.py, nothing here is best-effort — every function raises
HTTPException on failure so the caller gets a proper error response.
"""
from fastapi import HTTPException, status

from common.logging import get_logger
from common.models.auth import AdminUserItem, AuthTokenResponse, UserResponse
from common.supabase_client import get_auth_client, get_supabase_client

logger = get_logger(__name__)

_AUTH_UNAVAILABLE = "Authentication is unavailable — Supabase is not configured."

# DEV-62 roles. Granted by SQL only (`update user_profiles set role='admin' ...`)
# — no endpoint changes a role, so there is no escalation surface in the API.
DEFAULT_ROLE = "user"
ADMIN_ROLE = "admin"

# ponytail: the account list reads one page. Paginate if the user base outgrows it.
ADMIN_LIST_LIMIT = 100


def _require(client):
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_AUTH_UNAVAILABLE,
        )
    return client


def _get_auth_client():
    """GoTrue client for user-session calls (sign_in/get_user/admin). 503 if off.

    Separate from the data client so signing a user in can't downgrade the
    data client's PostgREST role and re-enable RLS — see supabase_client.py.
    """
    return _require(get_auth_client())


def _get_data_client():
    """Service-role client for .table() reads/writes (RLS bypassed). 503 if off."""
    return _require(get_supabase_client())


def _get_admin_client():
    """Service-role client for GoTrue *admin* calls (create_user, sign_out).

    Reuses the data client precisely because nothing ever signs a user into it,
    so its Authorization header stays the service key. Doing admin calls on the
    session client (_get_auth_client) would send whatever user JWT sign_in last
    stored there — and once that session is logged out, the admin endpoint 403s
    with "Session from session_id claim in JWT does not exist".
    """
    return _require(get_supabase_client())


def _fetch_profile(user_id: str) -> tuple[str, str]:
    """Return (username, role) for a user; ('', DEFAULT_ROLE) if no row exists.

    Read on every token verification, so the role is never baked into the JWT:
    a promotion or demotion in SQL takes effect on the caller's next request.
    """
    try:
        result = (
            _get_data_client()
            .table("user_profiles")
            .select("username, role")
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            return "", DEFAULT_ROLE
        row = result.data[0]
        return row.get("username") or "", row.get("role") or DEFAULT_ROLE
    except Exception as exc:
        logger.warning("Failed to fetch profile for %s: %s", user_id, exc)
        # Failing closed on the role: an unreadable profile is never an admin.
        return "", DEFAULT_ROLE


def register(email: str, password: str, username: str) -> AuthTokenResponse:
    """Create a new user (auto-confirmed), store their username, then sign in."""
    data = _get_data_client()

    # Check username uniqueness (case-insensitive)
    try:
        existing = (
            data.table("user_profiles")
            .select("user_id")
            .ilike("username", username)
            .execute()
        )
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Username uniqueness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )

    # Create GoTrue user (admin client → always service-role, never a user session)
    try:
        resp = _get_admin_client().auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        user_id = str(resp.user.id)
    except Exception as exc:
        _handle_auth_error(exc, "register")
        raise  # unreachable — _handle_auth_error always raises

    # Store username
    try:
        data.table("user_profiles").insert(
            {"user_id": user_id, "username": username}
        ).execute()
    except Exception as exc:
        logger.error("Failed to insert user_profiles for %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )

    # login() fetches the username we just inserted
    return login(email, password)


def login(email: str, password: str) -> AuthTokenResponse:
    """Sign in with email + password; returns access and refresh tokens."""
    client = _get_auth_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        session = response.session
        user = response.user
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Sign-in succeeded but no session was returned.",
            )
        user_id = str(user.id)
        username, role = _fetch_profile(user_id)
        return AuthTokenResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            user_id=user_id,
            email=user.email,
            username=username,
            role=role,
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_auth_error(exc, "login")


def logout(jwt: str) -> None:
    """Revoke the specific access token server-side.

    Failure is logged but does not propagate — the frontend always discards
    the token regardless, so a failed server-side revocation is not fatal.
    """
    try:
        _get_admin_client().auth.admin.sign_out(jwt)
    except Exception as exc:
        logger.warning("Server-side sign_out failed: %s", exc)


def get_user_from_token(jwt: str) -> UserResponse:
    """Verify a Supabase access token and return the user. Raises 401 on failure."""
    client = _get_auth_client()
    try:
        response = client.auth.get_user(jwt)
        user = response.user if response is not None else None
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = str(user.id)
        username, role = _fetch_profile(user_id)
        return UserResponse(user_id=user_id, email=user.email, username=username, role=role)
    except HTTPException:
        raise
    except Exception as exc:
        logger.info("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def list_accounts() -> list[AdminUserItem]:
    """Every account, newest first (DEV-62).

    GoTrue is the source of truth for existence and email; user_profiles supplies
    username and role. An account with no profile row still lists — as a plain
    user with an empty username — so a half-finished registration stays visible
    (and therefore deletable) instead of vanishing from the admin's view.
    """
    admin = _get_admin_client()
    data = _get_data_client()

    try:
        users = admin.auth.admin.list_users(per_page=ADMIN_LIST_LIMIT)
    except Exception as exc:
        _handle_auth_error(exc, "list_accounts")
        raise  # unreachable — _handle_auth_error always raises

    try:
        rows = (
            data.table("user_profiles").select("user_id, username, role").execute().data
        ) or []
    except Exception as exc:
        # Not degraded to empty profiles: that would render every account as a
        # plain user and hide who the admins are — worse than failing loudly.
        logger.error("Failed to read user_profiles for the account list: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The account list could not be loaded.",
        )

    profiles = {row["user_id"]: row for row in rows}

    def _item(u) -> AdminUserItem:
        user_id = str(u.id)
        profile = profiles.get(user_id) or {}
        return AdminUserItem(
            user_id=user_id,
            email=u.email or "",
            username=profile.get("username") or "",
            role=profile.get("role") or DEFAULT_ROLE,
            created_at=getattr(u, "created_at", None),
        )

    items = [_item(u) for u in users]
    return sorted(
        items,
        key=lambda i: i.created_at.isoformat() if i.created_at else "",
        reverse=True,
    )


def delete_account(user_id: str) -> None:
    """Delete a GoTrue user (DEV-62). Supabase cascades user_profiles and
    user_profile_data; the Dapr state store is deliberately NOT purged — see
    docs/adr/0003-admin-role.md.
    """
    try:
        _get_admin_client().auth.admin.delete_user(user_id)
    except Exception as exc:
        _handle_auth_error(exc, "delete_account")  # passes GoTrue's 404 through
    logger.info("Admin deleted account %s", user_id)


def _handle_auth_error(exc: Exception, context: str) -> None:
    """Translate GoTrue API errors to appropriate HTTP responses. Always raises."""
    try:
        from supabase_auth.errors import AuthApiError  # bundled with supabase-py as supabase-auth

        if isinstance(exc, AuthApiError):
            msg = getattr(exc, "message", None) or str(exc)
            # status may live on .status or .status_code depending on the version
            code = getattr(exc, "status", None) or getattr(exc, "status_code", None)
            if "already registered" in msg.lower() or "already exists" in msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists.",
                )
            if code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests — please wait before trying again.",
                )
            # Pass the actual Supabase message through for all other auth errors
            http_code = code if (code and 400 <= code < 600) else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=http_code, detail=msg)
    except (ImportError, HTTPException):
        raise

    logger.warning("Auth error during %s: %s", context, exc)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Authentication failed.",
    )
