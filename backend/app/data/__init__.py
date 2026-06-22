"""Static catalog data, ported from the frontend's data.js so the two stay in sync."""
import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent


@lru_cache
def load_careers() -> list[dict]:
    return json.loads((_DATA_DIR / "careers.json").read_text(encoding="utf-8"))


@lru_cache
def load_questions() -> list[dict]:
    return json.loads((_DATA_DIR / "questions.json").read_text(encoding="utf-8"))


# Valid question ids, e.g. {"q1", ..., "q10"} — used to validate submissions.
@lru_cache
def question_ids() -> frozenset[str]:
    return frozenset(q["id"] for q in load_questions())
