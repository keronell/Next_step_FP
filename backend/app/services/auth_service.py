"""Auth operations wrapping Supabase GoTrue.

Unlike persistence.py, nothing here is best-effort — every function raises
HTTPException on failure so the caller gets a proper error response.
"""
from fastapi import HTTPException, status

from app.core.logging import get_logger
from app.models.auth import AuthTokenResponse, SubmissionHistoryItem, UserResponse
from app.services.supabase_client import get_supabase_client

logger = get_logger(__name__)

_AUTH_UNAVAILABLE = "Authentication is unavailable — Supabase is not configured."


def _get_auth_client():
    """Return the Supabase client or raise 503 if Supabase is not configured."""
    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_AUTH_UNAVAILABLE,
        )
    return client


def register(email: str, password: str) -> AuthTokenResponse:
    """Create a new user (auto-confirmed) then sign in to return tokens."""
    client = _get_auth_client()
    try:
        client.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
    except Exception as exc:
        _handle_auth_error(exc, "register")
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
        return AuthTokenResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            user_id=str(user.id),
            email=user.email,
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
    client = _get_auth_client()
    try:
        client.auth.admin.sign_out(jwt)
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
        return UserResponse(user_id=str(user.id), email=user.email)
    except HTTPException:
        raise
    except Exception as exc:
        logger.info("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def claim_sessions(user_id: str, session_id: str) -> None:
    """Link prior anonymous submissions to a now-authenticated user.

    Only updates rows where user_id IS NULL so a row can't be re-claimed.
    """
    client = _get_auth_client()
    try:
        client.table("submissions").update({"user_id": user_id}).eq(
            "session_id", session_id
        ).is_("user_id", "null").execute()
    except Exception as exc:
        logger.warning(
            "claim_sessions failed for user %s / session %s: %s",
            user_id,
            session_id,
            exc,
        )


def get_user_submissions(user_id: str) -> list[SubmissionHistoryItem]:
    """Return the 20 most recent submissions for a user, newest first."""
    client = _get_auth_client()
    try:
        result = (
            client.table("submissions")
            .select("request_id, recommendations, selected_career, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return [
            SubmissionHistoryItem(
                request_id=row["request_id"],
                recommendations=row.get("recommendations") or [],
                selected_career=row.get("selected_career"),
                created_at=row.get("created_at"),
            )
            for row in (result.data or [])
        ]
    except Exception as exc:
        logger.warning("Failed to fetch submissions for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve submission history.",
        )


def _handle_auth_error(exc: Exception, context: str) -> None:
    """Translate GoTrue API errors to appropriate HTTP responses. Always raises."""
    try:
        from supabase_auth.errors import AuthApiError  # bundled with supabase-py as supabase-auth

        if isinstance(exc, AuthApiError):
            msg = getattr(exc, "message", str(exc))
            code = getattr(exc, "status", None)
            if "already registered" in msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists.",
                )
            if code == 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=msg
                )
            if code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests — please wait before trying again.",
                )
    except ImportError:
        pass

    logger.warning("Auth error during %s: %s", context, exc)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Authentication failed.",
    )
