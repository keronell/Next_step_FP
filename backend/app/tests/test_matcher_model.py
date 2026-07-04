"""Unit tests for the learned-matcher artifact loader and reason builder."""
import json

import pytest

from app.data import load_careers, load_questions
from app.services.feature_builder import FEATURE_VERSION, feature_names
from app.services.matcher_model import MatcherModel, MatcherModelError
from app.services.reason_builder import build_reasons

CAREERS = load_careers()
QUESTIONS = {q["id"]: q for q in load_questions()}
NAMES = feature_names(CAREERS)
CIDS = [c["id"] for c in CAREERS]


def tiny_artifact(**overrides) -> dict:
    """A structurally valid artifact: zero coefs except +1 on each career's own fit."""
    coef = [[0.0] * len(NAMES) for _ in CIDS]
    for i, cid in enumerate(CIDS):
        coef[i][NAMES.index(f"{cid}_fit")] = 1.0
    artifact = {
        "model_version": "test-v0",
        "feature_version": FEATURE_VERSION,
        "feature_names": NAMES,
        "careers": CIDS,
        "scaler_mean": [0.0] * len(NAMES),
        "scaler_scale": [1.0] * len(NAMES),
        "coef": coef,
        "intercept": [0.0] * len(CIDS),
        "label_source": "synthetic_llm",
    }
    artifact.update(overrides)
    return artifact


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(MatcherModelError):
        MatcherModel.load(tmp_path / "nope.json")


def test_feature_version_mismatch_raises():
    with pytest.raises(MatcherModelError):
        MatcherModel(tiny_artifact(feature_version="features-v999"))


def test_shape_mismatch_raises():
    with pytest.raises(MatcherModelError):
        MatcherModel(tiny_artifact(intercept=[0.0]))


def test_predict_proba_sums_to_one_and_ranks_fit():
    model = MatcherModel(tiny_artifact())
    vec = [0.0] * len(NAMES)
    vec[NAMES.index("frontend_fit")] = 1.0  # only frontend has fit signal
    probs = model.predict_proba(vec)
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert max(probs, key=probs.get) == "frontend"


def test_wrong_vector_length_raises():
    model = MatcherModel(tiny_artifact())
    with pytest.raises(MatcherModelError):
        model.predict_proba([0.0] * 3)


def test_contributions_center_to_zero_across_classes():
    model = MatcherModel(tiny_artifact())
    vec = [1.0] * len(NAMES)
    total = [0.0] * len(NAMES)
    for cid in CIDS:
        contrib = model.contributions(vec, cid)
        for j, name in enumerate(NAMES):
            total[j] += contrib[name]
    assert all(abs(t) < 1e-9 for t in total)


def test_roundtrip_via_file(tmp_path):
    p = tmp_path / "artifact.json"
    p.write_text(json.dumps(tiny_artifact()), encoding="utf-8")
    model = MatcherModel.load(p)
    assert model.careers == CIDS


def test_reasons_quote_answer_and_cap_at_four():
    frontend = next(c for c in CAREERS if c["id"] == "frontend")
    answers = {"q2": 0, "q9": 3}
    contributions = {
        "frontend_fit": 0.8, "frontend_sem": 0.5, "frontend_skill": 0.4,
        "q2": 0.6, "q9": 0.9, "q9_present": 0.1,
    }
    reasons = build_reasons(frontend, answers, contributions, ["React", "CSS"], QUESTIONS)
    assert 1 <= len(reasons) <= 4
    assert any("React" in r for r in reasons)
    joined = " ".join(reasons)
    assert QUESTIONS["q9"]["options"][3] in joined  # quotes the user's own words


def test_reasons_fallback_when_no_signal():
    frontend = next(c for c in CAREERS if c["id"] == "frontend")
    reasons = build_reasons(frontend, {}, {}, [], QUESTIONS)
    assert reasons == ["A direction worth exploring based on your responses"]


def test_negative_contributions_never_surface():
    frontend = next(c for c in CAREERS if c["id"] == "frontend")
    contributions = {"frontend_fit": -1.0, "frontend_sem": -0.5, "q2": -2.0}
    reasons = build_reasons(frontend, {"q2": 1}, contributions, [], QUESTIONS)
    assert reasons == ["A direction worth exploring based on your responses"]
