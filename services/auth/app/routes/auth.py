"""Auth routes — register, login, logout, me. (claim-sessions and
my-submissions live in history-service: they're submission-domain, the gateway
carves their exact paths out of /api/auth/.)

All routes require Supabase to be configured; they return 503 otherwise
(auth is never best-effort, unlike persistence).
"""
from fastapi import APIRouter, Depends

from app.deps import get_current_token, get_current_user
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


