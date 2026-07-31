"""matching-service test fixtures. Same strategy as the monolith suite: a fake
repository injected onto app.state (TestClient WITHOUT lifespan, so the real
ChromaDB store / embedding model are never loaded), external backends forced off."""
import json
import random
import sys
from pathlib import Path

_SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SERVICE.parent))  # services/  -> `common` package
sys.path.insert(0, str(_SERVICE))         # matching/  -> `app` package

from collections import Counter  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.repositories.career_repository import CareerCandidate, FakeCareerRepository  # noqa: E402
from app.services.feature_builder import FEATURE_VERSION, feature_names  # noqa: E402
from common.data import load_careers  # noqa: E402

_CAREERS = load_careers()
_NAMES = feature_names(_CAREERS)
_CIDS = [c["id"] for c in _CAREERS]


def tiny_artifact(**overrides) -> dict:
    """A structurally valid matcher artifact: zero coefs except +1 on each
    career's own fit. Shared by the loader and dispatch-seam suites."""
    coef = [[0.0] * len(_NAMES) for _ in _CIDS]
    for i, cid in enumerate(_CIDS):
        coef[i][_NAMES.index(f"{cid}_fit")] = 1.0
    artifact = {
        "model_version": "test-v0",
        "feature_version": FEATURE_VERSION,
        "feature_names": _NAMES,
        "careers": _CIDS,
        "scaler_mean": [0.0] * len(_NAMES),
        "scaler_scale": [1.0] * len(_NAMES),
        "coef": coef,
        "intercept": [0.0] * len(_CIDS),
        "label_source": "synthetic_llm",
    }
    artifact.update(overrides)
    return artifact


def write_artifact(tmp_path: Path, artifact: dict, name: str = "artifact.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(artifact), encoding="utf-8")
    return p


def nn_artifact(feature_names: list[str], careers: list[str], members: list[dict],
                **overrides) -> dict:
    """A structurally valid neural artifact. `members` are already-built layer
    stacks, so callers keep full control of the weights they reason about.

    This is the schema DEV-97's exporter has to emit: one shared scaler (every
    ensemble member standardizes on the same training statistics, so per-member
    scalers would be five copies of one thing), weights stored (out_features,
    in_features) exactly as the linear artifact's `coef` is."""
    artifact = {
        "model_version": "test-nn-v0",
        "model_type": "probability_averaged_mlp_ensemble",
        "feature_version": FEATURE_VERSION,
        "feature_names": feature_names,
        "careers": careers,
        "scaler_mean": [0.0] * len(feature_names),
        "scaler_scale": [1.0] * len(feature_names),
        "activation": "relu",
        "members": members,
        "label_source": "synthetic_llm",
    }
    artifact.update(overrides)
    return artifact


def dense_member(shapes: list[tuple[int, int]], seed: int) -> dict:
    """A member with pseudo-random weights, for tests that need a realistically
    shaped network rather than a hand-worked one. `shapes` are (out, in) pairs."""
    rng = random.Random(seed)
    return {
        "layers": [
            {
                "weight": [[rng.uniform(-1.0, 1.0) for _ in range(n_in)] for _ in range(n_out)],
                "bias": [rng.uniform(-0.5, 0.5) for _ in range(n_out)],
            }
            for n_out, n_in in shapes
        ]
    }


def full_size_nn_artifact(n_members: int = 3, hidden=(12, 8), seed: int = 7,
                          **overrides) -> dict:
    """A neural artifact over the REAL feature layout and career catalog, so the
    matching service can be driven end to end without a trained model."""
    shapes: list[tuple[int, int]] = []
    prev = len(_NAMES)
    for width in hidden:
        shapes.append((width, prev))
        prev = width
    shapes.append((len(_CIDS), prev))
    return nn_artifact(
        feature_names=_NAMES,
        careers=_CIDS,
        members=[dense_member(shapes, seed=seed + i) for i in range(n_members)],
        **overrides,
    )


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
