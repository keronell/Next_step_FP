"""Test fixtures. Routes/flow are tested against a FakeCareerRepository so no real
ChromaDB / embedding model is needed."""
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.data import load_careers
from app.main import app
from app.repositories.career_repository import CareerCandidate, FakeCareerRepository


@pytest.fixture(autouse=True)
def _supabase_disabled(monkeypatch):
    """Force Supabase off for every test, regardless of a developer's local
    backend/.env — persistence/reads must be no-ops in tests (see CLAUDE.md).
    Empty env vars take precedence over the .env file in pydantic-settings."""
    from app.core.config import get_settings
    from app.services import persistence
    from app.services.supabase_client import get_supabase_client

    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")  # never call OpenAI from tests
    # Clear before each test so the forced-empty env is what gets read. (Teardown
    # clearing is avoided: a test may monkeypatch _client to a plain function that
    # has no cache_clear, and that patch is still in place during teardown.)
    for cached in (get_settings, persistence._client, get_supabase_client):
        cached.cache_clear()
    yield


def make_candidates() -> list[CareerCandidate]:
    """One candidate per real career with plausible RAG signals."""
    careers = load_careers()
    sims = {
        "frontend": 0.82, "backend": 0.55, "data-science": 0.40,
        "devops": 0.30, "product-manager": 0.25, "ux-designer": 0.70,
    }
    markets = {
        "frontend": Counter({"react": 5, "css": 3, "typescript": 2, "redux": 1}),
        "ux-designer": Counter({"figma": 4, "user research": 2, "prototyping": 1}),
    }
    return [
        CareerCandidate(
            career=c,
            semantic_similarity=sims.get(c["id"], 0.2),
            market_skills=markets.get(c["id"], Counter()),
        )
        for c in careers
    ]


@pytest.fixture
def valid_answers() -> dict:
    return {f"q{i}": (i % 4) for i in range(1, 11)}


@pytest.fixture
def client_with_repo():
    """TestClient with a fake repository injected. Constructed WITHOUT the lifespan
    context manager so the real ChromaDB store / model are never loaded in tests."""
    app.state.repository = FakeCareerRepository(make_candidates())
    yield TestClient(app)
    app.state.repository = None


@pytest.fixture
def client_no_repo():
    """TestClient with no repository (simulates RAG store unavailable)."""
    app.state.repository = None
    yield TestClient(app)
