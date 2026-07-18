"""Auth dependencies for services that don't own GoTrue: verification is
delegated to auth-service via Dapr service invocation (GET /internal/verify),
which returns the UserResponse for a valid bearer token.

Error mapping mirrors the monolith's deps: no/invalid token -> 401,
auth-service unreachable or Dapr off -> 503 (auth is never best-effort);
get_current_user_optional never raises — anonymous flows must not break when
auth is down (and during the phased rollout, before auth-service exists).
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common import dapr
from common.logging import get_logger
from common.models.auth import UserResponse

logger = get_logger(__name__)

# Also the generic "something went wrong" detail for user-facing 5xx responses.
SAFE_UNAVAILABLE = "Career recommendations could not be generated at this time."

AUTH_APP_ID = "auth"
_AUTH_UNAVAILABLE = "Authentication is unavailable."

_bearer = HTTPBearer(auto_error=False)


def _verify(jwt: str) -> UserResponse:
    try:
        r = dapr.invoke(
            AUTH_APP_ID,
            "internal/verify",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    except dapr.DaprError:
        logger.warning("auth-service invocation failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_AUTH_UNAVAILABLE
        )
    if r.status_code == 200:
        return UserResponse(**r.json())
    try:
        detail = r.json().get("detail", _AUTH_UNAVAILABLE)
    except Exception:  # noqa: BLE001 - non-JSON error body
        detail = _AUTH_UNAVAILABLE
    if r.status_code in (401, 403):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _verify(credentials.credentials)


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse | None:
    if credentials is None:
        return None
    try:
        return _verify(credentials.credentials)
    except HTTPException:
        return None
