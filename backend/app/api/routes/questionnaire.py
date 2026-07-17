import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.deps import get_current_user_optional, get_repository
from app.core.logging import get_logger
from app.models.auth import UserResponse
from app.models.questionnaire import CareerSelection, QuestionnaireSubmission
from app.models.recommendation import RecommendationsResponse
from app.services.matching_service import match
from app.services.persistence import save_selection, save_submission

logger = get_logger(__name__)

router = APIRouter(prefix="/questionnaire")


@router.post("/submit", response_model=RecommendationsResponse)
def submit(
    submission: QuestionnaireSubmission,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: UserResponse | None = Depends(get_current_user_optional),
) -> RecommendationsResponse:
    # Resolve the repo inside the handler (not as a dependency) so body validation
    # errors return 422 before the 503-when-unavailable check fires.
    repo = get_repository(request)
    request_id = uuid.uuid4().hex
    answered = sum(1 for v in submission.answers.values() if v is not None)
    logger.info("Submission %s: %d answered questions", request_id, answered)

    candidates = repo.get_candidates(submission.answers)
    model = getattr(request.app.state, "matcher_model", None)
    recommendations = match(submission.answers, candidates, model=model)
    logger.info("Submission %s: returning %d recommendations", request_id, len(recommendations))

    # Best-effort persistence via Dapr pub/sub (DEV-38): the subscriber writes the
    # state store. The publish itself is deferred with BackgroundTasks so a slow
    # sidecar/broker can never delay this response — BackgroundTasks no longer
    # persists anything, it only pushes a ~1ms local publish off the response path.
    # created_at is minted HERE, not in the background task: a claim/selection can
    # land right after this response, and the marker time-bounds compare against
    # it — a late-run task would make this submission look newer than the claim.
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
    """Record which career the user opened. Best-effort, never blocks the UI.

    selected_at (click time) is minted here and travels in the event: the store
    applies a selection only to submissions that existed at click time, so a
    delayed event can never stamp an old choice onto a later retake.
    """
    logger.info("Session %s selected career %s", selection.session_id, selection.career_id)
    background_tasks.add_task(
        save_selection,
        selection.session_id,
        selection.career_id,
        datetime.now(timezone.utc).isoformat(),
    )
    return {"ok": True}
