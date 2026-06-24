"""Bridges the static career catalog with the ChromaDB RAG store, producing the
normalized candidates the matching service scores. The Fake variant lets route and
matching tests run without a real vector DB."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.logging import get_logger
from app.data import load_careers
from app.services import job_postings_service
from app.services.profile import build_profile
from app.services.rag_service import RagService

logger = get_logger(__name__)


@dataclass
class CareerCandidate:
    career: dict
    semantic_similarity: float | None  # None when the field returned no job ads
    market_skills: Counter = field(default_factory=Counter)


class CareerRepository:
    """Real repository: encodes the profile once and queries ChromaDB per career."""

    def __init__(self, rag: RagService, settings: Settings):
        self._rag = rag
        self._settings = settings

    def get_candidates(self, answers: dict[str, int | None]) -> list[CareerCandidate]:
        profile = build_profile(answers)
        embedding = self._rag.encode(profile)
        k = self._settings.rag_top_k

        candidates: list[CareerCandidate] = []
        seen: set[str] = set()
        for career in load_careers():
            if career["id"] in seen:
                continue
            seen.add(career["id"])
            similarity, skills = self._rag.query_field(embedding, career["field"], k)
            # Supplement ChromaDB's market skills with skills from Postgres job_postings.
            # No-op (empty Counter) when Supabase is unconfigured -> ChromaDB-only path.
            skills = skills + job_postings_service.skill_counts(career["field"], k)
            candidates.append(CareerCandidate(career, similarity, skills))

        retrieved = sum(1 for c in candidates if c.semantic_similarity is not None)
        logger.info("Retrieved RAG candidates for %d/%d careers", retrieved, len(candidates))
        return candidates


class FakeCareerRepository:
    """Test double: returns canned candidates without touching ChromaDB."""

    def __init__(self, candidates: list[CareerCandidate]):
        self._candidates = candidates

    def get_candidates(self, answers: dict[str, int | None]) -> list[CareerCandidate]:
        return self._candidates
