"""Submission-history routes. Paths keep their monolith-era /auth/ prefix — the
frontend calls them there and the gateway exact-matches these two out of
/api/auth/ (identity itself lives in auth-service; the CALLER is verified by
invoking auth's /internal/verify via common.auth_dep).

Contracts unchanged from the monolith: claim is best-effort past the 503 gate;
my-submissions raises 500 on store errors.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.services import submission_store
from common.auth_dep import get_current_user
from common.dapr import enabled as _dapr_enabled
from common.logging import get_logger
from common.models.auth import ClaimSessionsRequest, SubmissionHistoryItem, UserResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/auth")

_HISTORY_UNAVAILABLE = "Submission history is unavailable — the state store is not configured."


def _require_dapr() -> None:
    if not _dapr_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_HISTORY_UNAVAILABLE,
        )


@router.post("/claim-sessions")
def claim_sessions(
    body: ClaimSessionsRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> dict:
    """Link prior anonymous submissions to the now-authenticated user."""
    _require_dapr()
    try:
        claimed = submission_store.claim_sessions(current_user.user_id, body.session_id)
        logger.info("Claimed %d submissions for user %s", claimed, current_user.user_id)
    except Exception as exc:  # noqa: BLE001 - claim is best-effort past the gate
        logger.warning(
            "claim_sessions failed for user %s / session %s: %s",
            current_user.user_id,
            body.session_id,
            exc,
        )
    return {"ok": True}


@router.get("/my-submissions", response_model=list[SubmissionHistoryItem])
def my_submissions(
    current_user: UserResponse = Depends(get_current_user),
) -> list[SubmissionHistoryItem]:
    _require_dapr()
    try:
        return [
            SubmissionHistoryItem(
                request_id=record["request_id"],
                recommendations=record.get("recommendations") or [],
                selected_career=record.get("selected_career"),
                created_at=record.get("created_at"),
                profile=record.get("profile"),
            )
            for record in submission_store.get_user_submissions(current_user.user_id)
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to fetch submissions for user %s: %s", current_user.user_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve submission history.",
        )
