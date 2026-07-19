"""Question bank endpoint — serves the authoritative questionnaire from
app/data/questions.json (the same source used for submission validation and
profile building). The frontend fetches this on load and falls back to its
bundled copy in data.js when the backend is unreachable.
"""
from fastapi import APIRouter

from common.data import load_questions

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("")
def questions() -> list[dict]:
    return load_questions()
