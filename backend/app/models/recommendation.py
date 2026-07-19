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
    # Which scorer produced this rec: "formula-v1" or the loaded artifact's version.
    # Persisted with the submission so silver-model output stays distinguishable.
    model_version: str = "formula-v1"
    # The artifact's training-data warnings, embedded per-rec so persistence and
    # the history restore path keep them attached to model-derived results.
    model_caveats: list[str] = []


class RecommendationsResponse(BaseModel):
    request_id: str
    recommendations: list[Recommendation]
    # Provenance warnings embedded in the model artifact (training-data caveats).
    # Populated only when the learned matcher actually scored this response —
    # empty for the formula path, including the mid-request model-error fallback.
    model_caveats: list[str] = []
