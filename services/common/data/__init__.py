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


@lru_cache
def load_roadmaps() -> dict[str, dict]:
    return json.loads((_DATA_DIR / "roadmaps.json").read_text(encoding="utf-8"))


# Lowercased spelling -> canonical skill name ("reactjs" -> "React"). Shared by the
# roadmap requirements display map and the DEV-60 profile skill normalizer.
@lru_cache
def load_skill_aliases() -> dict[str, str]:
    raw = json.loads((_DATA_DIR / "skill_aliases.json").read_text(encoding="utf-8"))
    return {k.lower(): str(v).lower() for k, v in raw.get("aliases", {}).items()}


# Valid question ids, e.g. {"q1", ..., "q10"} — used to validate submissions.
@lru_cache
def question_ids() -> frozenset[str]:
    return frozenset(q["id"] for q in load_questions())


# Valid career ids, e.g. {"frontend", ...} — used to validate career selections.
@lru_cache
def career_ids() -> frozenset[str]:
    return frozenset(c["id"] for c in load_careers())
