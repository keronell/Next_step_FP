"""Pydantic models for the auth endpoints."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")

# Authorization roles (DEV-62). Two tiers today; add here (and to the DB hook's
# allow-list) to introduce more. `student` is the default for every new signup —
# it's the product's baseline user. `app_metadata.role` on the Supabase user is
# the source of truth; user_metadata is NOT (users can edit that themselves).
Role = Literal["student", "admin"]
DEFAULT_ROLE: Role = "student"
VALID_ROLES: frozenset[str] = frozenset(("student", "admin"))

# Privilege ordering: higher rank satisfies a lower-ranked gate. A route that
# requires "student" also admits "admin"; requiring "admin" admits only admins.
# Keep monotonic when adding tiers (e.g. moderator between the two).
_ROLE_RANK: dict[str, int] = {"student": 0, "admin": 100}


def has_privilege(user_role: str, required: Role) -> bool:
    """True if `user_role` is at least as privileged as `required`."""
    return _ROLE_RANK.get(user_role, -1) >= _ROLE_RANK[required]


def normalize_role(value: object) -> Role:
    """Coerce an arbitrary app_metadata value to a known role.

    Unknown / missing / malformed values fall back to the least-privileged
    default rather than raising — a user must never be *elevated* by a bad
    claim, and a missing claim (pre-DEV-62 accounts) means `student`.
    """
    return value if value in VALID_ROLES else DEFAULT_ROLE


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
    # Role at sign-in time so the frontend can guard UI without a second /me call.
    role: Role = DEFAULT_ROLE


class UserResponse(BaseModel):
    user_id: str
    email: str
    username: str
    # Authorization role, resolved from Supabase app_metadata (DEV-62). Defaults
    # to "student" so pre-existing accounts and any missing claim are safe.
    role: Role = DEFAULT_ROLE


class ClaimSessionsRequest(BaseModel):
    # Same charset the frontend mints; session ids become state-store keys.
    session_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{1,64}$")


class SubmissionHistoryItem(BaseModel):
    request_id: str
    recommendations: list[dict]
    selected_career: str | None
    created_at: datetime | None
