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
    # DEV-62: lets the SPA decide on the admin entry point straight after sign-in,
    # without a second /me round trip.
    role: str = "user"


class UserResponse(BaseModel):
    user_id: str
    email: str
    username: str
    # DEV-62 authorization role — `user` or `admin`. NOT an occupation (CONTEXT.md
    # reserves "Career" for that). Defaulted so every existing construction and
    # every service that parses this off /internal/verify keeps working untouched.
    role: str = "user"


class AdminUserItem(BaseModel):
    """One row of the admin account list: GoTrue identity + user_profiles fields."""
    user_id: str
    email: str
    username: str
    role: str
    created_at: datetime | None = None


class ClaimSessionsRequest(BaseModel):
    # Same charset the frontend mints; session ids become state-store keys.
    session_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{1,64}$")


class SubmissionHistoryItem(BaseModel):
    request_id: str
    recommendations: list[dict]
    selected_career: str | None
    created_at: datetime | None
    # The DEV-60 profile snapshot that produced these recommendations. Restoring a
    # past result must restore the profile it was scored with — otherwise the
    # roadmap pairs historical skill gaps with whatever profile is current.
    # None for submissions made before the profile step existed, or when skipped.
    profile: dict | None = None
