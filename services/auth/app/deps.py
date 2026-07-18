"""Auth-service dependencies: Bearer tokens verified DIRECTLY against Supabase
GoTrue — this is the one service that owns identity. Everyone else verifies by
invoking our /internal/verify (see common/auth_dep.py)."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services import auth_service
from common.models.auth import UserResponse

# auto_error=False so the optional variant can return None when no header is present
# instead of raising 403.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse:
    """Require a valid Bearer token. Raises 401 if missing or invalid."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_service.get_user_from_token(credentials.credentials)


def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Validate a Bearer token and return the raw JWT. Raises 401 if missing/invalid."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    auth_service.get_user_from_token(credentials.credentials)  # raises 401 if invalid
    return credentials.credentials


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse | None:
    """Return the current user if a valid token is present, else None.

    Never raises — routes that use this dependency always serve anonymous users too.
    """
    if credentials is None:
        return None
    try:
        return auth_service.get_user_from_token(credentials.credentials)
    except HTTPException:
        return None
