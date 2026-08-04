"""Response models. Carries every field the existing Results.jsx renders
(id, title, description, keySkills, icon, roadmapKey, matchPercent) plus the
explainability extras the UI may surface (score_breakdown, reasons, skills)."""
from pydantic import BaseModel


class ScoreBreakdown(BaseModel):
    semantic_similarity: float
    questionnaire_fit: float
    skill_overlap: float
    # DEV-60: present only when a non-empty self-input profile scored this request
    # (PROFILE_WEIGHTS path) — null on the formula path, which has no user skills to
    # compare. Optional rather than absent because this model is the public contract:
    # without it pydantic silently drops a component worth 20% of the score, and the
    # persisted record (raw dicts, never revalidated) would keep a field the live
    # response had thrown away.
    user_skill_match: float | None = None
    # ADR 0005 mitigation: present only when a `ranking_only` artifact scored this
    # request, where every displayed figure is the formula's. This is the model's own
    # probability — the number that selected and ordered nothing else on screen — kept
    # so the selection stays auditable from the response and the persisted history.
    # Declared here for the same reason user_skill_match is: an undeclared key is
    # dropped at serialization, and the persisted jsonb would then disagree with the
    # live response about how the recommendation was produced.
    model_probability: float | None = None


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
