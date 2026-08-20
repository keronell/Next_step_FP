"""Dispatch seam: the Matcher protocol and the load_matcher() factory.

These assert against the protocol rather than against MatcherModel, which is what
let the NN adapter (DEV-94) join as a second family without touching them. Its own
dispatch and conformance cases live in `test_matcher_nn.py`.
"""
import os
from pathlib import Path

import pytest

from app.services.matcher import Matcher, load_matcher
from app.services.matcher_model import MatcherModel, MatcherModelError

from tests.conftest import tiny_artifact
from tests.conftest import write_artifact as write

REPO_ROOT = Path(__file__).resolve().parents[3]
SHIPPED_ARTIFACT = REPO_ROOT / "data" / "models" / "matcher_logistic_v2.json"


def test_linear_artifact_dispatches_to_the_linear_implementation(tmp_path):
    p = write(tmp_path, tiny_artifact(model_type="multinomial_logistic_regression"))
    assert isinstance(load_matcher(p), MatcherModel)


def test_loaded_matcher_satisfies_the_protocol(tmp_path):
    """The conformance assertion the NN adapter must also pass unchanged."""
    p = write(tmp_path, tiny_artifact(model_type="multinomial_logistic_regression"))
    matcher = load_matcher(p)
    assert isinstance(matcher, Matcher)


def test_unknown_model_type_is_refused_by_name(tmp_path):
    # Refused, never adapted — same posture as a Feature Version mismatch.
    p = write(tmp_path, tiny_artifact(model_type="random_forest"))
    with pytest.raises(MatcherModelError, match="random_forest"):
        load_matcher(p)


def test_absent_model_type_is_refused(tmp_path):
    p = write(tmp_path, tiny_artifact())  # tiny_artifact carries no model_type
    with pytest.raises(MatcherModelError):
        load_matcher(p)


def test_missing_file_raises_the_catchable_error(tmp_path):
    # main.py only catches MatcherModelError; anything else crashes startup
    # instead of falling back to the formula.
    with pytest.raises(MatcherModelError):
        load_matcher(tmp_path / "nope.json")


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    # Short-circuits before os.geteuid, which does not exist on Windows and would
    # otherwise raise at import and break collection for this whole module.
    reason="POSIX directory permissions, and root ignores them",
)
def test_unsearchable_parent_raises_the_catchable_error(tmp_path):
    # A Path.exists() pre-check does NOT return False here - it raises
    # PermissionError, which the lifespan does not catch. Regression guard for
    # the probe being reintroduced ahead of the try.
    locked = tmp_path / "locked"
    locked.mkdir()
    artifact = locked / "m.json"
    artifact.write_text("{}", encoding="utf-8")
    locked.chmod(0o000)
    try:
        with pytest.raises(MatcherModelError):
            load_matcher(artifact)
    finally:
        locked.chmod(0o755)


def test_unconvertible_path_raises_the_catchable_error():
    # read_text() raises a bare ValueError on an embedded NUL where the old
    # exists() probe just returned False. Still has to reach the lifespan as
    # MatcherModelError, or startup dies instead of falling back.
    with pytest.raises(MatcherModelError):
        load_matcher("model\x00.json")


def test_malformed_json_raises_the_catchable_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(MatcherModelError):
        load_matcher(p)


def test_feature_version_mismatch_still_refused_through_the_factory(tmp_path):
    p = write(
        tmp_path,
        tiny_artifact(
            model_type="multinomial_logistic_regression", feature_version="features-v999"
        ),
    )
    with pytest.raises(MatcherModelError):
        load_matcher(p)


async def _matcher_after_startup(monkeypatch, artifact_path) -> object:
    """Run the real lifespan and return what it put on app.state.

    The RAG store is genuinely unavailable in tests, which the lifespan already
    handles by logging and setting repository=None — so this exercises the matcher
    branch without standing up ChromaDB.
    """
    from fastapi import FastAPI

    from app import main as main_module
    from common.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "matcher_model_path", str(artifact_path))
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    app = FastAPI()
    async with main_module.lifespan(app):
        return app.state.matcher_model


@pytest.mark.anyio
async def test_startup_refuses_an_unknown_model_type(monkeypatch, tmp_path):
    """Startup must dispatch, not just deserialize: a structurally valid artifact
    from an unsupported family is refused and the service falls back to the
    formula. Passes trivially if startup calls a concrete loader that ignores
    model_type."""
    p = write(tmp_path, tiny_artifact(model_type="random_forest"))
    assert await _matcher_after_startup(monkeypatch, p) is None


@pytest.mark.anyio
async def test_startup_loads_the_shipped_artifact(monkeypatch):
    matcher = await _matcher_after_startup(monkeypatch, SHIPPED_ARTIFACT)
    assert isinstance(matcher, Matcher)
    assert matcher.version == "matcher-logistic-v2"


def test_shipped_artifact_loads_through_the_factory():
    """DEV-88's evidence that the checked-in artifact is NOT stale: it is
    features-v4, matches the serving code, and loads. CLAUDE.md claimed the
    opposite until this ticket."""
    matcher = load_matcher(SHIPPED_ARTIFACT)
    assert isinstance(matcher, Matcher)
    assert isinstance(matcher, MatcherModel)  # the shipped family, today
    assert matcher.version == "matcher-logistic-v2"
    assert matcher.caveats
    # Fitted on OOF predictions from the artifact's exact fixed C=1.0
    # configuration; Phase 3's heterogeneous per-fold-Cs model produced 1.0.
    assert matcher.temperature == 1.05
