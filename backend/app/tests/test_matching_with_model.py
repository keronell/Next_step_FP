"""Phase 5 serving tests: learned-model path, formula fallback, shape parity."""
from collections import Counter

from app.data import load_careers
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
def _submit(client):
    resp = client.post("/api/questionnaire/submit", json={"answers": {"q1": 1}})
    assert resp.status_code == 200
    return resp.json()


def test_submit_surfaces_model_caveats_when_model_scores(client_with_repo):
    from app.main import app

    model = make_model("frontend")
    model.caveats = ["caveat one", "caveat two"]
    app.state.matcher_model = model
    try:
        body = _submit(client_with_repo)
        assert body["model_caveats"] == ["caveat one", "caveat two"]
        assert body["recommendations"][0]["model_version"] == "test-model-v0"
    finally:
        app.state.matcher_model = None


def test_submit_formula_path_has_empty_model_caveats(client_with_repo):
    body = _submit(client_with_repo)
    assert body["model_caveats"] == []
    assert body["recommendations"][0]["model_version"] == FORMULA_VERSION


def test_submit_model_error_fallback_drops_caveats(client_with_repo):
    from app.main import app

    model = make_model()
    model.caveats = ["should not surface"]
    model.feature_names = ["wrong"]  # forces fallback to the formula mid-request
    app.state.matcher_model = model
    try:
        body = _submit(client_with_repo)
        assert body["model_caveats"] == []
        assert body["recommendations"][0]["model_version"] == FORMULA_VERSION
    finally:
        app.state.matcher_model = None


def test_model_path_dedupes_candidates():
    frontend = CAREERS[0]
    cands = candidates() + [CareerCandidate(frontend, 0.9, Counter())]
    recs = match(ANSWERS, cands, model=make_model())
    assert len([r for r in recs if r["id"] == frontend["id"]]) == 1
