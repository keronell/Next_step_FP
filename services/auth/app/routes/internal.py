"""East-west verification endpoint (Dapr invocation only, never gateway-routed).

Other services forward the caller's bearer token here; a valid token answers
200 + UserResponse, anything else propagates 401/503 to the invoking sidecar —
common/auth_dep.py on the caller side mirrors those statuses.
"""
from fastapi import APIRouter, Depends

from app.deps import get_current_user
from common.models.auth import UserResponse

router = APIRouter(prefix="/internal")


@router.get("/verify", response_model=UserResponse)
def verify(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    return current_user
