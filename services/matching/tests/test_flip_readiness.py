"""DEV-99 flip readiness: the testable half of the ticket's acceptance criteria,
asserted rather than asserted-in-prose.

DEV-99 is human-gated and nothing here flips anything — `MATCHER_MODEL_PATH` stays
blank. What these tests do is make the claims the approver is being asked to rely
on *checkable*, because three of DEV-99's five acceptance criteria are statements
about runtime behaviour that had only ever been read off the source:

  - "a failed load still falls back to the formula"  -> the load-failure block
  - "the service ... logs the loaded model version"  -> the logging block
  - "clearing the variable restores the formula with no redeploy of code"
                                                     -> the rollback block

Each drives the REAL `main.lifespan` and then the real `/internal/match` scoring
path, so a regression in either the loader or the fallback breaks a test rather
than a deployment.

The final block is different in kind: two `xfail(strict=True)` tests pinning a gap
DEV-99 found rather than a behaviour it verified. See their docstrings.
"""
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.services.matcher import load_matcher
from app.services.matching_service import FORMULA_VERSION, match

from tests.conftest import make_candidates, tiny_artifact
from tests.conftest import write_artifact as write

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS = REPO_ROOT / "data" / "models"
LINEAR_ARTIFACT = MODELS / "matcher_logistic_v2.json"
NN_ARTIFACT = MODELS / "matcher_nn_v1.json"
# The value backend/.env:23 still carries. It is a 6-career features-v1 artifact and
# must stay refused: see test_the_artifact_backend_env_points_at_is_still_refused.
STALE_ARTIFACT = MODELS / "matcher_logistic_v1.json"

# Spans the whole bank rather than q1-q10, so the vector the model scores is the one
# a real submission produces (q11-q18 are the pure discriminators).
ANSWERS = {f"q{i}": (i % 4) for i in range(1, 19)}


async def matcher_after_startup(monkeypatch, path) -> object:
    """Whatever the real lifespan puts on app.state for this MATCHER_MODEL_PATH.

    ChromaDB is genuinely absent under test, which the lifespan already handles by
    logging and setting repository=None — so this exercises the matcher branch
    without standing up the RAG store.
    """
    from app import main as main_module
    from common.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "matcher_model_path", str(path))
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    probe = FastAPI()
    async with main_module.lifespan(probe):
        return probe.state.matcher_model


def served(model) -> list[dict]:
    """What /internal/match's scoring step returns for ANSWERS under `model`."""
    return match(ANSWERS, make_candidates(), model=model)


def formula_output() -> list[dict]:
    return match(ANSWERS, make_candidates())


# ------------------------------------------------------- AC: a failed load falls back
# load_matcher raises MatcherModelError on every failure path and the lifespan catches
# exactly that. These prove the consequence end to end — that the request the user
# actually gets back is the formula's — rather than that the exception type lines up.
def _failure_cases(tmp_path) -> list[tuple[str, Path]]:
    return [
        ("stale feature layout", STALE_ARTIFACT),
        ("missing file", tmp_path / "absent.json"),
        ("unknown family", write(tmp_path, tiny_artifact(model_type="random_forest"), "u.json")),
        (
            "feature version mismatch",
            write(
                tmp_path,
                tiny_artifact(
                    model_type="multinomial_logistic_regression",
                    feature_version="features-v999",
                ),
                "fv.json",
            ),
        ),
    ]


@pytest.mark.anyio
async def test_every_load_failure_serves_exactly_the_formula(monkeypatch, tmp_path):
    """Not merely "falls back" — the response is identical to the no-model one.

    A fallback that engaged but left `model_version` or `model_caveats` stamped
    would still satisfy a weaker assertion, and would tell a user their result came
    from a model that never scored it.
    """
    baseline = formula_output()
    for label, path in _failure_cases(tmp_path):
        loaded = await matcher_after_startup(monkeypatch, path)
        assert loaded is None, f"{label}: lifespan kept an unusable matcher"
        recs = served(loaded)
        assert recs == baseline, f"{label}: served output diverged from the formula"
        assert all(r["model_version"] == FORMULA_VERSION for r in recs), label
        assert all(r["model_caveats"] == [] for r in recs), label


def test_the_artifact_backend_env_points_at_is_still_refused():
    """`backend/.env:23` names matcher_logistic_v1.json, and compose's interpolation
    scope keeps that value away from the matching container (the `environment:` key
    overrides `env_file:`). This test covers the other half of that safety argument:
    even if the value DID arrive, the artifact is refused rather than served.

    Skipped rather than failed when the file is absent — it is retained for history
    and deleting it is a legitimate cleanup, at which point the risk is gone.
    """
    from app.services.matcher import MatcherModelError

    if not STALE_ARTIFACT.exists():
        pytest.skip(f"{STALE_ARTIFACT.name} has been removed - nothing left to refuse")
    with pytest.raises(MatcherModelError, match="feature_version"):
        load_matcher(STALE_ARTIFACT)


# ------------------------------------------------ AC: the service logs the model version
@pytest.mark.anyio
@pytest.mark.parametrize(
    "artifact,expected_version",
    [(LINEAR_ARTIFACT, "matcher-logistic-v2"), (NN_ARTIFACT, "matcher-nn-v1")],
    ids=["linear", "neural"],
)
async def test_startup_logs_the_loaded_model_version(
    monkeypatch, caplog, artifact, expected_version
):
    """The operator's only confirmation that a flip took effect is this log line."""
    if not artifact.exists():
        pytest.skip(f"{artifact.name} not present - run its exporter")
    with caplog.at_level(logging.INFO, logger="app.main"):
        loaded = await matcher_after_startup(monkeypatch, artifact)
    assert loaded is not None and loaded.version == expected_version
    assert any(expected_version in r.getMessage() for r in caplog.records), (
        "startup did not log the loaded model version"
    )


@pytest.mark.anyio
async def test_the_neural_artifact_loads_through_the_real_lifespan(monkeypatch):
    """The linear artifact already has this (test_matcher.py). The neural one is what
    DEV-99 would actually turn on, and until now nothing drove it through startup."""
    if not NN_ARTIFACT.exists():
        pytest.skip("matcher_nn_v1.json not present - run data/scripts/export_nn_model.py")
    from app.services.matcher_nn import NeuralMatcher

    loaded = await matcher_after_startup(monkeypatch, NN_ARTIFACT)
    assert isinstance(loaded, NeuralMatcher)
    assert loaded.version == "matcher-nn-v1"
    assert loaded.temperature == 0.80  # non-inert: it sharpens the served percentages


# ------------------------------------------------------------------ AC: rollback works
@pytest.mark.anyio
async def test_clearing_the_variable_restores_the_formula_in_the_same_process(monkeypatch):
    """The rollback criterion, proved rather than asserted: same interpreter, same
    imported modules, no reload of anything — only the setting changes.

    That is what makes "no redeploy of code" true. The artifact is read once in the
    lifespan and reached only through `app.state`, so a restart with the variable
    cleared is a complete rollback of the scoring path.
    """
    if not NN_ARTIFACT.exists():
        pytest.skip("matcher_nn_v1.json not present - run data/scripts/export_nn_model.py")

    loaded = await matcher_after_startup(monkeypatch, NN_ARTIFACT)
    assert loaded is not None
    model_recs = served(loaded)
    assert all(r["model_version"] == "matcher-nn-v1" for r in model_recs)

    cleared = await matcher_after_startup(monkeypatch, "")
    assert cleared is None
    assert served(cleared) == formula_output()


def test_rollback_does_not_reach_recommendations_already_persisted():
    """The half of the rollback story that is NOT restored, stated as a test so it is
    not discovered in production.

    `model_version` and `model_caveats` are embedded per recommendation and the
    submission record stores recommendations as opaque dicts
    (`SubmissionHistoryItem.recommendations: list[dict]`). Clearing the variable
    changes what NEW submissions are scored with; it rewrites nothing already in the
    state store. A user's history therefore stays permanently mixed, and
    `History.jsx` re-renders each row's stored `matchPercent` — with no caveat
    rendering of its own, which lives only in `Results.jsx`.

    This is provenance working as designed, not a defect. It is a rollback *limit*,
    and the DEV-99 approver should know it before flipping rather than after.
    """
    if not NN_ARTIFACT.exists():
        pytest.skip("matcher_nn_v1.json not present - run data/scripts/export_nn_model.py")
    recs = served(load_matcher(NN_ARTIFACT))

    # This is what a persisted history row keeps verbatim.
    persisted = json.loads(json.dumps(recs))
    assert all(r["model_version"] == "matcher-nn-v1" for r in persisted)
    assert all(r["model_caveats"] for r in persisted)
    assert all(isinstance(r["matchPercent"], int) for r in persisted)


# ------------------------------------------- the gap DEV-99 found: ADR 0002's mitigation
# `matcher_nn_v1.json` declares deployment.status "ranking_only" and
# deployment.match_percent "FALL BACK TO THE FORMULA - this model's percentages are
# uncalibrated". ADR 0002 defines that mitigation as the thing which makes a model
# failing the ECE half shippable at all.
#
# Nothing in the serving path reads it. The two tests below are strict xfails: they
# fail today (which is the finding) and will fail LOUDER as XPASS the moment the
# mitigation lands, at which point whoever implemented it deletes the markers. They
# are the record that the gap was known, not an accepted state.
#
# Deliberately NOT written as an assertion of the current behaviour: pinning
# `matchPercent == round(probability * 100)` as correct would make the defect a
# specification, and the next reader would have no way to tell.
NEEDS_MITIGATION = pytest.mark.xfail(
    strict=True,
    reason=(
        "ADR 0002's mitigation is documented in the artifact, the ADR and CONTEXT.md, "
        "and implemented nowhere - DEV-99 finding. Remove this marker when it lands."
    ),
)


def test_the_shipped_artifact_still_declares_ranking_only():
    """The artifact's half of the contract, asserted OUTSIDE the xfail below.

    It belongs outside deliberately: inside a strict xfail, an exporter that stopped
    emitting `deployment` would raise KeyError, pytest would record that as the
    expected failure, and the regression would stay green — the marker would hide
    exactly the change that matters most.
    """
    if not NN_ARTIFACT.exists():
        pytest.skip("matcher_nn_v1.json not present - run data/scripts/export_nn_model.py")
    deployment = json.loads(NN_ARTIFACT.read_text(encoding="utf-8"))["deployment"]
    assert deployment["status"] == "ranking_only"
    assert "FORMULA" in deployment["match_percent"]


@NEEDS_MITIGATION
def test_the_serving_path_can_see_a_ranking_only_declaration():
    """The root cause. `Matcher` declares feature_names/version/caveats and no
    `deployment`, so both implementations drop the block on load and the scoring code
    has no way to ask whether this artifact is allowed to display its percentages.
    Every possible mitigation needs this first.
    """
    if not NN_ARTIFACT.exists():
        pytest.skip("matcher_nn_v1.json not present - run data/scripts/export_nn_model.py")
    matcher = load_matcher(NN_ARTIFACT)
    assert getattr(matcher, "deployment", None) is not None


@NEEDS_MITIGATION
def test_a_ranking_only_model_does_not_display_its_own_probability():
    """The consequence. `matching_service._match_model` sets
    `matchPercent = round(probs[cid] * 100)` unconditionally, so today the displayed
    percentage IS the uncalibrated probability the caveat warns about — the model's
    pooled OOF ECE is 0.139 against a 0.10 floor.

    The invariant asserted is the negative one ADR 0002 actually requires: the number
    on screen is not derived from this model's probability. Asserting the positive
    form (equality with the formula's percentage) is not yet possible — `_match_formula`
    returns only its own TOP_N, so the formula's score for a career the model ranked
    but the formula did not is not computed anywhere. That refactor is part of the
    cost, and it is why this is not a one-line fix.

    Compared against the model's UNROUNDED probability, not against the response's
    `score`. `score` is `round(prob, 3)` while `matchPercent` is `round(prob * 100)`,
    so the two already disagree for a few percent of recommendations purely by
    rounding — an invariant built on `score` would fail and pass for reasons that
    have nothing to do with the mitigation.
    """
    if not NN_ARTIFACT.exists():
        pytest.skip("matcher_nn_v1.json not present - run data/scripts/export_nn_model.py")
    from app.services import feature_builder

    matcher = load_matcher(NN_ARTIFACT)
    cands = make_candidates()
    careers = [c.career for c in cands]
    probs = matcher.predict_proba(
        feature_builder.build_feature_vector(
            ANSWERS,
            careers,
            {c.career["id"]: c.semantic_similarity for c in cands},
            {c.career["id"]: c.market_skills for c in cands},
        )
    )

    recs = served(matcher)
    assert recs
    assert all(r["matchPercent"] != round(probs[r["id"]] * 100) for r in recs)
