"""Public questionnaire endpoints. Matching is delegated to matching-service
(Dapr invocation); persistence is published to the `submissions`/`selections`
topics for history-service to consume (DEV-38 pub/sub, unchanged)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends

from app.matching_client import match_remote
from app.services.persistence import save_selection, save_submission
from common.auth_dep import get_current_user_optional
from common.logging import get_logger
from common.models.auth import UserResponse
from common.models.questionnaire import CareerSelection, QuestionnaireSubmission
from common.models.recommendation import RecommendationsResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/questionnaire")


@router.post("/submit", response_model=RecommendationsResponse)
def submit(
    submission: QuestionnaireSubmission,
    background_tasks: BackgroundTasks,
    current_user: UserResponse | None = Depends(get_current_user_optional),
) -> RecommendationsResponse:
    request_id = uuid.uuid4().hex
    answered = sum(1 for v in submission.answers.values() if v is not None)
    logger.info("Submission %s: %d answered questions", request_id, answered)

    recommendations = match_remote(submission.answers)  # 503 when matching is down
    logger.info("Submission %s: returning %d recommendations", request_id, len(recommendations))

    # created_at minted HERE (see monolith questionnaire.py rationale: marker
    # time bounds compare against it, a late background mint would skew them).
    background_tasks.add_task(
        save_submission,
        request_id,
        submission.answers,
        recommendations,
        submission.session_id,
        current_user.user_id if current_user else None,
        datetime.now(timezone.utc).isoformat(),
    )

    return RecommendationsResponse(request_id=request_id, recommendations=recommendations)


@router.post("/select")
def select(selection: CareerSelection, background_tasks: BackgroundTasks) -> dict:
    """Record which career the user opened. Best-effort, never blocks the UI."""
    logger.info("Session %s selected career %s", selection.session_id, selection.career_id)
    background_tasks.add_task(
        save_selection,
        selection.session_id,
        selection.career_id,
        datetime.now(timezone.utc).isoformat(),
    )
    return {"ok": True}
