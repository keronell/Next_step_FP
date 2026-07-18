"""matching-service test fixtures. Same strategy as the monolith suite: a fake
repository injected onto app.state (TestClient WITHOUT lifespan, so the real
ChromaDB store / embedding model are never loaded), external backends forced off."""
import sys
from pathlib import Path

_SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SERVICE.parent))  # services/  -> `common` package
sys.path.insert(0, str(_SERVICE))         # matching/  -> `app` package

from collections import Counter  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.repositories.career_repository import CareerCandidate, FakeCareerRepository  # noqa: E402
from common.data import load_careers  # noqa: E402


@pytest.fixture(autouse=True)
def _backends_disabled(monkeypatch):
    """Force Supabase AND Dapr off for every test (DAPR_ENABLED must be the
    string "false" — pydantic can't parse "" as bool)."""
    from common import dapr
    from common.config import get_settings
    from common.supabase_client import get_auth_client, get_supabase_client

    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DAPR_ENABLED", "false")
    for cached in (get_settings, get_supabase_client, get_auth_client, dapr._http):
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
    from app.main import app

    app.state.repository = FakeCareerRepository(make_candidates())
    yield TestClient(app)
    app.state.repository = None


@pytest.fixture
def client_no_repo():
    from app.main import app

    app.state.repository = None
    yield TestClient(app)
