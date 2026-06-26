"""Pydantic models for the auth endpoints."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AuthCredentials(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8)

    @field_validator("email")
    @classmethod
    def basic_email_shape(cls, v: str) -> str:
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("invalid email address")
        return v.lower().strip()


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str


class UserResponse(BaseModel):
    user_id: str
    email: str


class ClaimSessionsRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class SubmissionHistoryItem(BaseModel):
    request_id: str
    recommendations: list[dict]
    selected_career: str | None
    created_at: datetime | None
