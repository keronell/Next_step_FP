"""Response models. Carries every field the existing Results.jsx renders
(id, title, description, keySkills, icon, roadmapKey, matchPercent) plus the
explainability extras the UI may surface (score_breakdown, reasons, skills)."""
from pydantic import BaseModel


class ScoreBreakdown(BaseModel):
    semantic_similarity: float
    questionnaire_fit: float
    skill_overlap: float


class Recommendation(BaseModel):
    id: str
    title: str
    description: str
    keySkills: list[str]
    icon: str
    roadmapKey: str
    matchPercent: int
    score: float
    score_breakdown: ScoreBreakdown
    reasons: list[str]
    matched_skills: list[str]
    missing_skills: list[str]


class RecommendationsResponse(BaseModel):
    request_id: str
    recommendations: list[Recommendation]
