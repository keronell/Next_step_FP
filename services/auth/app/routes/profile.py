"""Self-input profile routes (DEV-60). Auth required — a profile is account data.

Delete is PUT with empty sections: the three sections are edited as one document,
so there is nothing a DELETE would express that an empty PUT does not.
"""
from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.services import profile_service
from common.models.auth import UserResponse
from common.models.profile import UserProfile

router = APIRouter(prefix="/profile")


@router.get("", response_model=UserProfile)
def get_profile(current_user: UserResponse = Depends(get_current_user)) -> UserProfile:
    return profile_service.get_profile(current_user.user_id)


@router.put("", response_model=UserProfile)
def put_profile(
    profile: UserProfile, current_user: UserResponse = Depends(get_current_user)
) -> UserProfile:
    return profile_service.save_profile(current_user.user_id, profile)
