"""Request/response models for east-west (Dapr service invocation) endpoints.

These are the wire contracts between services — keep them in common so caller
and callee can never drift.
"""
from pydantic import BaseModel, Field

from common.models.profile import UserProfile


class MatchRequest(BaseModel):
    answers: dict[str, int | None] = Field(..., description="Validated questionnaire answers")
    # DEV-60 self-input profile. Optional: the step is skippable, and a missing or
    # empty profile must score exactly like the pre-DEV-60 formula.
    profile: UserProfile | None = None


class MatchResponse(BaseModel):
    recommendations: list[dict]


class FieldSkillsResponse(BaseModel):
    counts: dict[str, int]
    n_ads: int
