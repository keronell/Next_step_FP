"""Auth routes — register, login, logout, me, claim-sessions, my-submissions.

All routes require Supabase to be configured; they return 503 otherwise
(auth is never best-effort, unlike persistence).
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_token, get_current_user
from app.models.auth import (
    AuthCredentials,
    AuthTokenResponse,
    ClaimSessionsRequest,
    RegisterRequest,
    SubmissionHistoryItem,
    UserResponse,
)
from app.services import auth_service

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


@router.post("/claim-sessions")
def claim_sessions(
    body: ClaimSessionsRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> dict:
    """Link prior anonymous submissions to the now-authenticated user."""
    auth_service.claim_sessions(current_user.user_id, body.session_id)
    return {"ok": True}


@router.get("/my-submissions", response_model=list[SubmissionHistoryItem])
def my_submissions(
    current_user: UserResponse = Depends(get_current_user),
) -> list[SubmissionHistoryItem]:
    return auth_service.get_user_submissions(current_user.user_id)
