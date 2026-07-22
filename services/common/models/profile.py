"""Self-input user profile (DEV-60) — the first matching input that is genuinely
about the USER rather than the job market.

Wire contract shared by three hops: the frontend POSTs it inside
QuestionnaireSubmission, questionnaire-service forwards it in MatchRequest, and
auth-service stores it as one jsonb row. Keep it here so none of them can drift.

Caps are trust-boundary validation, not tidiness: this payload rides on an
unauthenticated endpoint (submit accepts anonymous callers) and every string
eventually reaches an embedding model and an LLM prompt.
"""
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

MAX_ENTRIES = 10       # per section (experience, projects)
MAX_SKILLS = 40
MAX_TECHNOLOGIES = 20  # per project
MAX_MONTHS = 720       # 60 years — anything beyond is a typo, not a career

# Strip BEFORE length checks — min_length counts whitespace, so a bare `min_length=1`
# accepts role="   ". That entry then makes is_empty false while contributing nothing,
# which stamps the profile model version and replaces the market skill signals for what
# is really an empty profile.
_Required = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_Optional = Annotated[str, StringConstraints(strip_whitespace=True)]


def _clean_list(values: list[str], limit: int) -> list[str]:
    """Strip, drop empties, dedupe case-insensitively (first spelling wins), cap."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw).strip()[:60]
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out[:limit]


class ExperienceEntry(BaseModel):
    role: _Required = Field(..., max_length=120)
    context: _Optional = Field("", max_length=120)  # company / school / freelance
    duration_months: int | None = Field(None, ge=0, le=MAX_MONTHS)
    description: _Optional = Field("", max_length=600)


class ProjectEntry(BaseModel):
    name: _Required = Field(..., max_length=120)
    description: _Optional = Field("", max_length=600)
    technologies: list[str] = Field(default_factory=list)

    @field_validator("technologies")
    @classmethod
    def clean_technologies(cls, values: list[str]) -> list[str]:
        return _clean_list(values, MAX_TECHNOLOGIES)


class UserProfile(BaseModel):
    experience: list[ExperienceEntry] = Field(default_factory=list, max_length=MAX_ENTRIES)
    projects: list[ProjectEntry] = Field(default_factory=list, max_length=MAX_ENTRIES)
    skills: list[str] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, values: list[str]) -> list[str]:
        return _clean_list(values, MAX_SKILLS)

    @property
    def is_empty(self) -> bool:
        """A profile the user skipped (or cleared) must score exactly like no profile."""
        return not (self.experience or self.projects or self.skills)
