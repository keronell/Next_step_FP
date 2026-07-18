"""auth-service test fixtures: Supabase forced off (503 contract) unless a test
patches the client accessors with fakes — same strategy as the monolith suite."""
import sys
from pathlib import Path

_SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SERVICE.parent))  # services/ -> `common` package
sys.path.insert(0, str(_SERVICE))         # auth/     -> `app` package

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _backends_disabled(monkeypatch):
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


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)
