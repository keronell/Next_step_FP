"""East-west endpoints (Dapr service invocation only — the gateway never routes
/internal/*). questionnaire-service calls /internal/match; roadmap-service calls
/internal/field-skills for the DEV-59 market-requirements mining."""
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.deps import get_repository
from app.services.matching_service import match
from common.auth_dep import SAFE_UNAVAILABLE
from common.models.internal import FieldSkillsResponse, MatchRequest, MatchResponse

router = APIRouter(prefix="/internal")


@router.post("/match", response_model=MatchResponse)
def match_endpoint(req: MatchRequest, request: Request) -> MatchResponse:
    repo = get_repository(request)  # 503 while the RAG store is unavailable
    model = getattr(request.app.state, "matcher_model", None)
    candidates = repo.get_candidates(req.answers)
    return MatchResponse(recommendations=match(req.answers, candidates, model=model))


@router.get("/field-skills/{field}", response_model=FieldSkillsResponse)
def field_skills(
    field: str,
    request: Request,
    sample_size: int = Query(default=100, ge=1, le=500),
) -> FieldSkillsResponse:
    rag = getattr(request.app.state, "rag", None)
    if rag is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SAFE_UNAVAILABLE
        )
    counts, n_ads = rag.field_skills(field, sample_size)
    return FieldSkillsResponse(counts=dict(counts), n_ads=n_ads)
