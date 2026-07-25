"""Admin routes (DEV-62) — the only privileged surface in the app.

Lives in auth-service because both operations are identity operations: the list
merges GoTrue with user_profiles, and the delete is a GoTrue admin call. Every
route is behind require_admin; the SPA hiding the page is presentation only.
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.deps import require_admin
from app.services import auth_service
from common.models.auth import AdminUserItem, UserResponse

# Supabase user ids are uuids and the id is interpolated into a GoTrue admin URL —
# constrain the segment so nothing else can be (same reasoning as history-service's
# _REQUEST_ID_PATTERN).
_USER_ID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

router = APIRouter(prefix="/admin")


@router.get("/users", response_model=list[AdminUserItem])
def list_users(_: UserResponse = Depends(require_admin)) -> list[AdminUserItem]:
    return auth_service.list_accounts()


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str = Path(..., pattern=_USER_ID_PATTERN),
    current_user: UserResponse = Depends(require_admin),
) -> Response:
    # Self-deletion is the realistic accident — the admin's own row is in the very
    # list they are clicking through, and the role can only be restored in SQL.
    #
    # Case-insensitive: Postgres parses uuids case-insensitively, so an uppercased
    # copy of your own id addresses your own account while comparing unequal to the
    # lowercase id GoTrue hands back — that spelling would walk straight past this
    # guard and delete the caller.
    if user_id.lower() == current_user.user_id.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )
    auth_service.delete_account(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
