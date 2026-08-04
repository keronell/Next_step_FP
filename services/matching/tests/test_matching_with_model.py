"""Phase 5 serving tests: learned-model path, formula fallback, shape parity.

"Shape parity" here means the *response* shape. Numerical parity between a fitted
estimator and the code that serves it lives with the exporters, in
`data/scripts/tests/test_export_model.py` (linear) and `test_export_nn_model.py`
(neural) — only the training venv has both runtimes.
"""
from collections import Counter
from pathlib import Path

import pytest

from common.data import load_careers
from app.repositories.career_repository import CareerCandidate
from app.services.feature_builder import FEATURE_VERSION, feature_names
from app.services.matcher_model import MatcherModel
from app.services.matching_service import FORMULA_VERSION, match

CAREERS = load_careers()
NAMES = feature_names(CAREERS)
CIDS = [c["id"] for c in CAREERS]
ANSWERS = {f"q{i}": (i % 4) for i in range(1, 11)}


def make_model(favorite: str = "frontend") -> MatcherModel:
    """Valid artifact whose only signal is a big intercept on `favorite`."""
    return MatcherModel({
        "model_version": "test-model-v0",
        "feature_version": FEATURE_VERSION,
        "feature_names": NAMES,
        "careers": CIDS,
        "scaler_mean": [0.0] * len(NAMES),
        "scaler_scale": [1.0] * len(NAMES),
        "coef": [[0.0] * len(NAMES) for _ in CIDS],
        "intercept": [5.0 if cid == favorite else 0.0 for cid in CIDS],
        "label_source": "synthetic_llm",
    })


def candidates():
    return [CareerCandidate(c, 0.5, Counter({"react": 3})) for c in CAREERS]


def test_model_path_ranks_by_probability_and_stamps_version():
    recs = match(ANSWERS, candidates(), model=make_model("ux-designer"))
    assert recs[0]["id"] == "ux-designer"
    assert all(r["model_version"] == "test-model-v0" for r in recs)
    assert recs[0]["matchPercent"] == round(recs[0]["score"] * 100)


def test_model_and_formula_paths_have_identical_shape():
    with_model = match(ANSWERS, candidates(), model=make_model())
    formula = match(ANSWERS, candidates())
    assert len(with_model) == len(formula) == 3
    for a, b in zip(with_model, formula):
        assert set(a.keys()) == set(b.keys())
        assert set(a["score_breakdown"].keys()) == set(b["score_breakdown"].keys())
    assert all(r["model_version"] == FORMULA_VERSION for r in formula)


def test_broken_model_falls_back_to_formula():
    model = make_model()
    model.feature_names = ["wrong"]  # forces the layout check to fail
    recs = match(ANSWERS, candidates(), model=model)
    assert recs == match(ANSWERS, candidates())
    assert all(r["model_version"] == FORMULA_VERSION for r in recs)


def test_no_model_is_exactly_the_formula_path():
    assert match(ANSWERS, candidates(), model=None) == match(ANSWERS, candidates())


def test_model_path_handles_missing_market_data():
    cands = [CareerCandidate(c, None, Counter()) for c in CAREERS]
    recs = match(ANSWERS, cands, model=make_model())
    assert recs
    for r in recs:
        assert r["score_breakdown"]["semantic_similarity"] == 0.0
        assert r["score_breakdown"]["skill_overlap"] == 0.0
        assert r["matched_skills"] == []


# ---------------------------------------------------------------- caveat propagation
# The artifact's caveats are embedded per recommendation, because /internal/match
# is the only thing questionnaire-service sees — it derives its response-level
# field from these recs, and the persisted jsonb keeps them attached.
def _match(client):
    resp = client.post("/internal/match", json={"answers": {"q1": 1}})
    assert resp.status_code == 200
    return resp.json()["recommendations"]


def test_match_embeds_model_caveats_when_model_scores(client_with_repo):
    from app.main import app

    model = make_model("frontend")
    model.caveats = ["caveat one", "caveat two"]
    app.state.matcher_model = model
    try:
        recs = _match(client_with_repo)
        assert all(r["model_caveats"] == ["caveat one", "caveat two"] for r in recs)
        assert recs[0]["model_version"] == "test-model-v0"
    finally:
        app.state.matcher_model = None


def test_match_formula_recs_carry_empty_caveats(client_with_repo):
    recs = _match(client_with_repo)
    assert all(r["model_caveats"] == [] for r in recs)
    assert recs[0]["model_version"] == FORMULA_VERSION


def test_match_model_error_fallback_drops_caveats(client_with_repo):
    from app.main import app

    model = make_model()
    model.caveats = ["should not surface"]
    model.feature_names = ["wrong"]  # forces fallback to the formula mid-request
    app.state.matcher_model = model
    try:
        recs = _match(client_with_repo)
        assert all(r["model_caveats"] == [] for r in recs)
        assert recs[0]["model_version"] == FORMULA_VERSION
    finally:
        app.state.matcher_model = None


def test_model_path_dedupes_candidates():
    frontend = CAREERS[0]
    cands = candidates() + [CareerCandidate(frontend, 0.9, Counter())]
    recs = match(ANSWERS, cands, model=make_model())
    assert len([r for r in recs if r["id"] == frontend["id"]]) == 1


# ------------------------------------------------- the shipped artifact, end to end
# The tests above prove the plumbing with a stub whose caveats are hand-set. This one
# closes the chain on the REAL exported artifact, which is what DEV-97's acceptance
# criterion actually asks ("a test proves they reach the recommendations response").
# The distinction matters here specifically: matcher_nn_v1 fails Gate 1's mitigable
# ECE half, and the caveat carrying that mitigation is the only thing that tells a
# consumer its percentages are uncalibrated. If it were dropped anywhere between the
# artifact and the response, the model would look calibrated all the way to the UI.
NN_ARTIFACT = Path(__file__).resolve().parents[3] / "data" / "models" / "matcher_nn_v1.json"


def test_the_shipped_neural_artifacts_caveats_reach_the_recommendations(client_with_repo):
    if not NN_ARTIFACT.exists():
        pytest.skip(f"{NN_ARTIFACT} not present — run data/scripts/export_nn_model.py")
    from app.main import app
    from app.services.matcher import load_matcher

    matcher = load_matcher(NN_ARTIFACT)
    app.state.matcher_model = matcher
    try:
        recs = _match(client_with_repo)
        assert recs
        for r in recs:
            assert r["model_caveats"] == matcher.caveats
            assert r["model_version"] == matcher.version
        # Named rather than merely non-empty: "some caveats arrived" would still pass
        # if the ADR 0005 mitigation were the one that went missing.
        assert any("NOT calibrated" in c for c in recs[0]["model_caveats"])
        assert any("bank-consistent" in c for c in recs[0]["model_caveats"])
    finally:
        app.state.matcher_model = None


def test_non_finite_probabilities_fall_back_to_the_formula():
    """Load-time validation cannot catch inf/NaN produced DURING inference.

    Finite weights can still overflow, and on the ranking_only path nothing else
    raises -- the formula supplies matchPercent, score and the breakdown -- so a NaN
    probability would reach `score_breakdown.model_probability` and fail at response
    serialization, outside the fallback. `_match_model` raises instead, which
    `match()` catches, so the user gets the formula's answer and valid JSON.
    """
    import json

    from app.services import feature_builder
    from app.services.matching_service import FORMULA_VERSION, match
    from common.data import load_careers

    class NonFinite:
        version = "non-finite-v1"
        caveats: list[str] = []
        deployment = {"status": "ranking_only"}

        def __init__(self, names):
            self.feature_names = names

        def predict_proba(self, vector):
            return {"frontend": float("nan")}

        def contributions(self, vector, career_id):
            return {}

    from tests.conftest import make_candidates

    names = feature_builder.feature_names(load_careers())
    answers = {f"q{i}": i % 4 for i in range(1, 19)}
    recs = match(answers, make_candidates(), model=NonFinite(names))

    assert recs, "expected the formula's recommendations, not an empty list"
    assert all(r["model_version"] == FORMULA_VERSION for r in recs)
    json.dumps(recs, allow_nan=False)  # would raise if a NaN survived
