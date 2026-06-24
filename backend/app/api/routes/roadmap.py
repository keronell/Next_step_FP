from fastapi import APIRouter, HTTPException

from app.services.roadmap_service import get_roadmap

router = APIRouter(prefix="/roadmap")


@router.get("/{career_id}")
def roadmap(career_id: str) -> dict:
    data = get_roadmap(career_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"no roadmap for career '{career_id}'")
    return data
