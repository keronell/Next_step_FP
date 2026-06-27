from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.auth import UserResponse
from app.services import roadmap_progress_service
from app.services.roadmap_service import get_roadmap

router = APIRouter(prefix="/roadmap")


class RoadmapContext(BaseModel):
    """Optional personalization signals from the matching result."""

    profile: str | None = None
    missing_skills: list[str] = []


class ProgressUpdate(BaseModel):
    """The full set of completed node ids for a career roadmap (last-write-wins)."""

    completed_nodes: list[str] = []


@router.get("/{career_id}")
def roadmap(career_id: str) -> dict:
    """Static roadmap (no personalization)."""
    data = get_roadmap(career_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"no roadmap for career '{career_id}'")
    return data


@router.post("/{career_id}")
def roadmap_personalized(career_id: str, ctx: RoadmapContext) -> dict:
    """Personalized roadmap when OpenAI is configured; static fallback otherwise."""
    data = get_roadmap(career_id, profile=ctx.profile, missing_skills=ctx.missing_skills)
    if data is None:
        raise HTTPException(status_code=404, detail=f"no roadmap for career '{career_id}'")
    return data


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
