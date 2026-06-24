from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.roadmap_service import get_roadmap

router = APIRouter(prefix="/roadmap")


class RoadmapContext(BaseModel):
    """Optional personalization signals from the matching result."""

    profile: str | None = None
    missing_skills: list[str] = []


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
