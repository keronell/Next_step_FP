"""Auth routes — register, login, logout, me. (claim-sessions and
my-submissions live in history-service: they're submission-domain, the gateway
carves their exact paths out of /api/auth/.)

All routes require Supabase to be configured; they return 503 otherwise
(auth is never best-effort, unlike persistence).
"""
from fastapi import APIRouter, Depends

from app.deps import get_current_token, get_current_user, require_role
from app.services import auth_service
from common.models.auth import (
    AuthCredentials,
    AuthTokenResponse,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=AuthTokenResponse)
def register(req: RegisterRequest) -> AuthTokenResponse:
    return auth_service.register(req.email, req.password, req.username)


@router.post("/login", response_model=AuthTokenResponse)
def login(credentials: AuthCredentials) -> AuthTokenResponse:
    return auth_service.login(credentials.email, credentials.password)


@router.post("/logout")
def logout(token: str = Depends(get_current_token)) -> dict:
    auth_service.logout(token)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
def me(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    return current_user


@router.get("/admin/check", response_model=UserResponse)
def admin_check(current_user: UserResponse = Depends(require_role("admin"))) -> UserResponse:
    """Reference admin-only route (DEV-62): 200 only for admins, 403 otherwise.

    This is the canonical example of gating a route on a role — copy the
    `Depends(require_role("admin"))` pattern (from common.auth_dep in any other
    service) onto real admin features as they land. Also lets the frontend
    confirm elevated access server-side rather than trusting the token claim.
    """
    return current_user


