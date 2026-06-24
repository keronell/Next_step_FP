"""Request model for questionnaire submission.

Accepts the frontend's real shape: { "answers": { "q1": 0..3 | null, ... } }.
Values are 0-3 (Likert option index) or null (skipped). Unknown keys are rejected
so a malformed payload fails fast with HTTP 422.
"""
from pydantic import BaseModel, Field, field_validator

from app.data import career_ids, question_ids


class QuestionnaireSubmission(BaseModel):
    answers: dict[str, int | None] = Field(
        ...,
        description="Map of question id (q1..q10) to chosen option value 0-3, or null if skipped.",
    )
    # Anonymous browser session id (localStorage UUID). Optional so older clients and
    # tests still validate; used to link this submission to a later career selection.
    session_id: str | None = None

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers: dict[str, int | None]) -> dict[str, int | None]:
        if not answers:
            raise ValueError("answers must not be empty")

        valid_ids = question_ids()
        unknown = set(answers) - valid_ids
        if unknown:
            raise ValueError(f"unknown question ids: {sorted(unknown)}")

        for qid, val in answers.items():
            if val is not None and not (0 <= val <= 3):
                raise ValueError(f"answer for {qid} must be 0-3 or null, got {val}")

        # At least one real (non-null) answer is required to compute anything.
        if all(v is None for v in answers.values()):
            raise ValueError("at least one question must be answered")

        return answers


class CareerSelection(BaseModel):
    """The career a user clicked into, tied back to their session for tracking."""

    session_id: str = Field(..., min_length=1)
    career_id: str

    @field_validator("career_id")
    @classmethod
    def validate_career_id(cls, career_id: str) -> str:
        if career_id not in career_ids():
            raise ValueError(f"unknown career id: {career_id!r}")
        return career_id
