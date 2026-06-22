"""Thin wrapper over the existing ChromaDB `job_ads` store.

Loads the embedding model + collection ONCE (at app startup), then per request
encodes the user's profile and runs one filtered query per career field. The store
is built by data/scripts/build_rag.py (cosine space, all-MiniLM-L6-v2) — we only
read it here, never re-ingest.
"""
from __future__ import annotations

import json
from collections import Counter

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RagUnavailableError(RuntimeError):
    """Raised when the ChromaDB store is missing, empty, or cannot be queried."""


class RagService:
    def __init__(self, collection, model, count: int):
        self._collection = collection
        self._model = model
        self.count = count

    @classmethod
    def create(cls, settings: Settings) -> "RagService":
        """Connect to the persisted collection and load the model. Raises
        RagUnavailableError if the store is missing or empty."""
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            client = chromadb.PersistentClient(path=settings.chroma_path)
            collection = client.get_collection(name=settings.chroma_collection)
            count = collection.count()
        except Exception as exc:  # missing dir / collection / chroma error
            raise RagUnavailableError(
                f"could not open ChromaDB collection '{settings.chroma_collection}' "
                f"at '{settings.chroma_path}': {exc}"
            ) from exc

        if count == 0:
            raise RagUnavailableError(
                f"ChromaDB collection '{settings.chroma_collection}' is empty — "
                "run data/scripts/build_rag.py first"
            )

        logger.info("Loading embedding model '%s'", settings.embed_model)
        model = SentenceTransformer(settings.embed_model)
        logger.info("ChromaDB collection '%s' loaded (%d documents)",
                    settings.chroma_collection, count)
        return cls(collection, model, count)

    def encode(self, text: str) -> list[float]:
        return self._model.encode([text])[0].tolist()

    def query_field(self, embedding: list[float], field: str, k: int) -> tuple[float | None, Counter]:
        """Return (mean semantic similarity, skill-frequency Counter) for the top-k
        job ads in `field`. similarity is None when the field has no ads."""
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where={"field": field},
            include=["metadatas", "distances"],
        )
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        if not distances:
            return None, Counter()

        # Cosine distance -> similarity. Clamp to [0,1] (distance can drift slightly >1).
        sims = [max(0.0, min(1.0, 1.0 - d)) for d in distances]
        similarity = sum(sims) / len(sims)

        skills: Counter = Counter()
        for meta in metadatas:
            raw = meta.get("skills") if meta else None
            if not raw:
                continue
            try:
                for s in json.loads(raw):
                    if s:
                        skills[str(s).strip().lower()] += 1
            except (json.JSONDecodeError, TypeError):
                continue

        return similarity, skills
