"""Unit tests for the linear matcher's inference/attribution and the reason builder.

Loading and dispatch live in test_matcher.py, at the seam.
"""
import math

import pytest

from common.data import load_careers, load_questions
from app.services.feature_builder import feature_names
from app.services.matcher_model import MatcherModel, MatcherModelError
from app.services.reason_builder import build_reasons

from tests.conftest import tiny_artifact

CAREERS = load_careers()
QUESTIONS = {q["id"]: q for q in load_questions()}
NAMES = feature_names(CAREERS)
CIDS = [c["id"] for c in CAREERS]


def test_feature_version_mismatch_raises():
    with pytest.raises(MatcherModelError):
        MatcherModel(tiny_artifact(feature_version="features-v999"))


def test_shape_mismatch_raises():
    with pytest.raises(MatcherModelError):
        MatcherModel(tiny_artifact(intercept=[0.0]))


def test_caveats_default_to_empty_list():
    assert MatcherModel(tiny_artifact()).caveats == []


def test_valid_caveats_are_kept():
    model = MatcherModel(tiny_artifact(caveats=["warning one", "warning two"]))
    assert model.caveats == ["warning one", "warning two"]


@pytest.mark.parametrize("bad", ["a bare string", ["ok", 42], {"not": "a list"}, 7])
def test_malformed_caveats_fail_at_load(bad):
    # Must fail HERE (load time -> formula fallback engages), never mid-request
    # when response serialization rejects a non-string entry.
    with pytest.raises(MatcherModelError):
        MatcherModel(tiny_artifact(caveats=bad))


def test_predict_proba_sums_to_one_and_ranks_fit():
    model = MatcherModel(tiny_artifact())
    vec = [0.0] * len(NAMES)
    vec[NAMES.index("frontend_fit")] = 1.0  # only frontend has fit signal
    probs = model.predict_proba(vec)
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert max(probs, key=probs.get) == "frontend"


def test_temperature_divides_logits_before_the_softmax():
    """T=2 on a hand-worked artifact: only frontend_fit fires, so the logits are
    2.0 for frontend and 0.0 for the other 15 careers. Tempered, that is 1.0 and
    0.0, giving frontend e/(e+15). Expected value derived from the softmax
    definition, not from the implementation."""
    model = MatcherModel(tiny_artifact(temperature=2.0))
    vec = [0.0] * len(NAMES)
    vec[NAMES.index("frontend_fit")] = 2.0
    probs = model.predict_proba(vec)
    expected = math.e / (math.e + (len(CIDS) - 1))
    assert probs["frontend"] == pytest.approx(expected)
    assert sum(probs.values()) == pytest.approx(1.0)


def test_temperature_defaults_to_one_and_is_inert():
    """The shipped artifact carries T=1.0, so the default path must be identical
    to an explicit 1.0 — this is what makes applying it a no-op change today."""
    vec = [0.0] * len(NAMES)
    vec[NAMES.index("frontend_fit")] = 2.0
    assert MatcherModel(tiny_artifact()).predict_proba(vec) == (
        MatcherModel(tiny_artifact(temperature=1.0)).predict_proba(vec)
    )


@pytest.mark.parametrize("bad", [0, -1.0, "2.0", None, True, float("inf"), float("nan")])
def test_malformed_temperature_fails_at_load(bad):
    # Same contract as caveats: reject at load so the formula fallback engages,
    # rather than serving percentages divided by a nonsense scalar. T=0 divides by
    # zero and T<0 inverts the ranking outright.
    with pytest.raises(MatcherModelError):
        MatcherModel(tiny_artifact(temperature=bad))


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


def test_contributions_stay_complete_under_temperature():
    """Attribution must explain the logit that actually produced the served
    probability, at any T. Anchored on the softmax identity
    log(P(a)/P(b)) == logit_a - logit_b: centering cancels in the difference and
    tiny_artifact's intercepts are zero, so the summed contributions must
    reproduce that log-ratio exactly. Fails if only one of the two methods is
    tempered — which is the regression DEV-91's non-1.0 T would otherwise ship.
    """
    model = MatcherModel(tiny_artifact(temperature=2.5))
    vec = [0.0] * len(NAMES)
    for i, cid in enumerate(CIDS):
        vec[NAMES.index(f"{cid}_fit")] = 0.5 * i
    probs = model.predict_proba(vec)
    a, b = CIDS[0], CIDS[-1]
    summed = sum(model.contributions(vec, a).values()) - sum(
        model.contributions(vec, b).values()
    )
    assert summed == pytest.approx(math.log(probs[a] / probs[b]))


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


# ------------------------------------------------- deployment block (ADR 0005)
def test_deployment_absent_means_unrestricted():
    """Silence must keep meaning today's behaviour.

    `matcher_logistic_v2.json` carries no `deployment` block and is Deployable, so a
    default of "restricted" would change the served output of the incumbent artifact
    the moment this parsing landed.
    """
    assert MatcherModel(tiny_artifact()).deployment is None


def test_deployment_ranking_only_is_kept():
    artifact = tiny_artifact(deployment={"status": "ranking_only", "ranking": "this model"})
    assert MatcherModel(artifact).deployment["status"] == "ranking_only"


@pytest.mark.parametrize(
    "bad",
    [
        {"status": "rankingonly"},   # the typo that must not grant permission
        {"status": "RANKING_ONLY"},  # status matching is exact, not case-folded
        {"status": None},
        {},                          # a block with no status decides nothing
        "ranking_only",              # a bare string, not the object the schema says
        [],
    ],
)
def test_unrecognised_deployment_fails_at_load(bad):
    """Fail closed, at load, so the formula fallback engages.

    The permissive alternative -- treat anything unrecognised as unrestricted -- would
    let a single typo silently hand an uncalibrated model permission to display its own
    percentages, which is the exact harm ADR 0005's mitigation exists to prevent. A
    load failure is loud and lands on the safe side.
    """
    with pytest.raises(MatcherModelError):
        MatcherModel(tiny_artifact(deployment=bad))
