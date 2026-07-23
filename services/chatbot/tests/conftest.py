"""chatbot-service test fixtures — same pattern as roadmap/history: no sidecar,
no Ollama; every test monkeypatches the seams (dapr, ollama_client) by name."""
import sys
from pathlib import Path

_SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SERVICE.parent))  # services/ -> `common` package
sys.path.insert(0, str(_SERVICE))         # chatbot/  -> `app` package

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _backends_disabled(monkeypatch):
    from common import dapr
    from common.config import get_settings

    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DAPR_ENABLED", "false")
    for cached in (get_settings, dapr._http):
        cached.cache_clear()
    yield


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def as_user(monkeypatch):
    """Authenticate every request as a fixed user (bypasses the auth-service
    invocation that common.auth_dep normally performs)."""
    from common import auth_dep
    from common.models.auth import UserResponse

    monkeypatch.setattr(
        auth_dep,
        "_verify",
        lambda jwt: UserResponse(
            user_id="user-uuid-123", email="user@example.com", username="testuser"
        ),
    )
    return {"Authorization": "Bearer valid-token"}
