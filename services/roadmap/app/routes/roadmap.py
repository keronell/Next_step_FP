from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from common.auth_dep import get_current_user
from common.models.auth import UserResponse
from app.services import roadmap_progress_service
from app.services.roadmap_service import get_roadmap, inject_requirements

router = APIRouter(prefix="/roadmap")

# DEV-82: every route here is behind the login wall, matching the assessment that
# leads to them. The API stops at *authentication* — it does not check that the
# caller was actually recommended this career. That stricter "unlocked" rule
# (CONTEXT.md) lives in the SPA, which already holds the recommendation; enforcing
# it here would make every roadmap fetch call history-service. See
# docs/adr/0002-roadmap-access.md.


class ProgressUpdate(BaseModel):
    """The full set of completed node ids for a career roadmap (last-write-wins)."""

    completed_nodes: list[str] = []


@router.get("/{career_id}")
def roadmap(career_id: str, _: UserResponse = Depends(get_current_user)) -> dict:
    """The curated roadmap, bare. Requires auth."""
    data = get_roadmap(career_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"no roadmap for career '{career_id}'")
    return data


@router.post("/{career_id}")
def roadmap_with_market(
    career_id: str, request: Request, _: UserResponse = Depends(get_current_user)
) -> dict:
    """The curated roadmap enriched with job-ad-derived requirements (DEV-59): an
    'In Demand Now' section of Required/Advantage skills mined from the career field's
    job ads. The requirements source is absent in tests / when the RAG store is down,
    so this degrades to the plain roadmap.

    This is the only thing separating it from the GET above — the roadmap itself no
    longer varies per user, so any request body is ignored (older clients still send
    one). It stays a POST because that is what the SPA already calls.
    """
    req_service = getattr(request.app.state, "requirements", None)
    requirements = req_service.get_requirements(career_id) if req_service else None

    data = get_roadmap(career_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"no roadmap for career '{career_id}'")
    return inject_requirements(data, requirements)


@router.get("/{career_id}/progress")
def get_progress(
    career_id: str, current_user: UserResponse = Depends(get_current_user)
) -> dict:
    """Completed node ids for the current user's roadmap. Requires auth."""
    return {
        "completed_nodes": roadmap_progress_service.get_progress(
            current_user.user_id, career_id
        )
    }


@router.post("/{career_id}/progress")
def save_progress(
    career_id: str,
    body: ProgressUpdate,
    current_user: UserResponse = Depends(get_current_user),
) -> dict:
    """Replace the completed node set for the current user's roadmap. Requires auth."""
    return {
        "completed_nodes": roadmap_progress_service.save_progress(
            current_user.user_id, career_id, body.completed_nodes
        )
    }
