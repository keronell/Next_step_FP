"""Pydantic models for the auth endpoints."""
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")


class AuthCredentials(BaseModel):
    """Used for login (email + password only)."""
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8)

    @field_validator("email")
    @classmethod
    def basic_email_shape(cls, v: str) -> str:
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("invalid email address")
        return v.lower().strip()


class RegisterRequest(BaseModel):
    """Used for registration (email + password + username)."""
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8)
    username: str = Field(..., min_length=3, max_length=30)

    @field_validator("email")
    @classmethod
    def basic_email_shape(cls, v: str) -> str:
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("invalid email address")
        return v.lower().strip()

    @field_validator("username")
    @classmethod
    def username_chars(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("username may only contain letters, digits, and underscores")
        return v


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str
    username: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    username: str


class ClaimSessionsRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class SubmissionHistoryItem(BaseModel):
    request_id: str
    recommendations: list[dict]
    selected_career: str | None
    created_at: datetime | None
