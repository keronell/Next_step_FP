"""Request/response models for east-west (Dapr service invocation) endpoints.

These are the wire contracts between services — keep them in common so caller
and callee can never drift.
"""
from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    answers: dict[str, int | None] = Field(..., description="Validated questionnaire answers")


class MatchResponse(BaseModel):
    recommendations: list[dict]


class FieldSkillsResponse(BaseModel):
    counts: dict[str, int]
    n_ads: int
