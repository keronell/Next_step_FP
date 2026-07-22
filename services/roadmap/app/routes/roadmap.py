from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from common.auth_dep import get_current_user
from common.models.auth import UserResponse
from common.models.profile import UserProfile
from common.profile_text import profile_sentences
from app.services import roadmap_progress_service
from app.services.roadmap_service import get_roadmap, inject_requirements

router = APIRouter(prefix="/roadmap")


class RoadmapContext(BaseModel):
    """Optional personalization signals from the matching result."""

    profile: str | None = None
    missing_skills: list[str] = []
    # DEV-60 self-input profile. Sent structured rather than pre-rendered so the
    # prose is built by the SAME helper matching uses — the frontend never has to
    # know how a profile reads as a sentence.
    profile_data: UserProfile | None = None

    def profile_text(self) -> str | None:
        if self.profile:
            return self.profile
        sentences = profile_sentences(self.profile_data)
        return " ".join(sentences) if sentences else None


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
def roadmap_personalized(career_id: str, ctx: RoadmapContext, request: Request) -> dict:
    """Personalized roadmap when OpenAI is configured; static fallback otherwise.

    Also enriches the roadmap with job-ad-derived requirements (DEV-59): an 'In Demand
    Now' section of Required/Advantage skills mined from the career field's job ads.
    The requirements source is absent in tests / when the RAG store is down, so this
    degrades to the plain roadmap.
    """
    req_service = getattr(request.app.state, "requirements", None)
    requirements = req_service.get_requirements(career_id) if req_service else None
    market_required = [r["skill"] for r in (requirements or {}).get("required", [])]

    data = get_roadmap(
        career_id,
        profile=ctx.profile_text(),
        missing_skills=ctx.missing_skills,
        market_required=market_required,
    )
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
