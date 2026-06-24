import uuid

from fastapi import APIRouter, BackgroundTasks, Request

from app.api.deps import get_repository
from app.core.logging import get_logger
from app.models.questionnaire import QuestionnaireSubmission
from app.models.recommendation import RecommendationsResponse
from app.services.matching_service import match
from app.services.persistence import save_submission

logger = get_logger(__name__)

router = APIRouter(prefix="/questionnaire")


@router.post("/submit", response_model=RecommendationsResponse)
def submit(
    submission: QuestionnaireSubmission,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RecommendationsResponse:
    # Resolve the repo inside the handler (not as a dependency) so body validation
    # errors return 422 before the 503-when-unavailable check fires.
    repo = get_repository(request)
    request_id = uuid.uuid4().hex
    answered = sum(1 for v in submission.answers.values() if v is not None)
    logger.info("Submission %s: %d answered questions", request_id, answered)

    candidates = repo.get_candidates(submission.answers)
    recommendations = match(submission.answers, candidates)
    logger.info("Submission %s: returning %d recommendations", request_id, len(recommendations))

    # Best-effort persistence after the response is sent (never blocks the user).
    background_tasks.add_task(
        save_submission,
        request_id,
        submission.answers,
        recommendations,
    )

    return RecommendationsResponse(request_id=request_id, recommendations=recommendations)
