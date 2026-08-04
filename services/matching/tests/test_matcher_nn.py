"""The neural serving path: numpy forward pass and adaptive integrated gradients.

Expected values here come from hand-worked networks, not from re-running the
implementation's own arithmetic. The two-member fixture below is small enough that
its logits are derivable on paper, which is what makes the ensemble-averaging
assertions independent of the code under test.
"""
import math

import pytest

from app.services.matcher import Matcher, load_matcher
from app.services.matcher_model import MatcherModelError
from app.services.matcher_nn import NeuralMatcher

from tests.conftest import full_size_nn_artifact, nn_artifact, write_artifact

# --------------------------------------------------------------- hand-worked net
# Two features, two careers, one hidden layer of two ReLU units, identity scaler.
#
#   layer 1: W = I, b = 0            -> h = relu(z)
#   layer 2: W = [[k, -k], [-k, k]]  -> u = [k(h1-h2), -k(h1-h2)]
#
# At z = [2, 1] both hidden units are active, so h = z and u = [k, -k]. The
# softmax of [k, -k] is [sigmoid(2k), 1 - sigmoid(2k)] — computable by hand.
IDENTITY_LAYER = {"weight": [[1.0, 0.0], [0.0, 1.0]], "bias": [0.0, 0.0]}


def antisymmetric_member(k: float) -> dict:
    return {
        "layers": [
            IDENTITY_LAYER,
            {"weight": [[k, -k], [-k, k]], "bias": [0.0, 0.0]},
        ]
    }


def two_member_artifact(**overrides) -> dict:
    """Members with k = 1 and k = 2, so at z = [2, 1] their logits are [1, -1]
    and [2, -2]. sigmoid(2) and sigmoid(4) are the hand-checkable member
    probabilities."""
    return nn_artifact(
        feature_names=["f0", "f1"],
        careers=["alpha", "beta"],
        members=[antisymmetric_member(1.0), antisymmetric_member(2.0)],
        **overrides,
    )


VECTOR = [2.0, 1.0]
SIGMOID_2 = 0.8807970779778823  # member k=1: softmax([1, -1])[0]
SIGMOID_4 = 0.9820137900379085  # member k=2: softmax([2, -2])[0]
MEAN_PROBABILITY = (SIGMOID_2 + SIGMOID_4) / 2  # 0.9314054340078954
# softmax of the MEAN LOGIT [1.5, -1.5] — the quantity we deliberately do NOT serve.
SIGMOID_3 = 0.9525741268224334


# ------------------------------------------------------------ dispatch and load
def test_neural_artifact_dispatches_to_the_neural_implementation(tmp_path):
    p = write_artifact(tmp_path, two_member_artifact())
    assert isinstance(load_matcher(p), NeuralMatcher)


def test_loaded_neural_matcher_satisfies_the_protocol(tmp_path):
    """The same conformance assertion the linear implementation passes."""
    p = write_artifact(tmp_path, two_member_artifact())
    assert isinstance(load_matcher(p), Matcher)


def test_feature_version_mismatch_is_refused(tmp_path):
    p = write_artifact(tmp_path, two_member_artifact(feature_version="features-v999"))
    with pytest.raises(MatcherModelError, match="feature_version"):
        load_matcher(p)


def test_layer_chain_that_does_not_compose_is_refused(tmp_path):
    """Shapes are read from the artifact, so an artifact whose layers cannot be
    multiplied together must fail at LOAD time — where main.py falls back to the
    formula — rather than raising mid-request."""
    broken = antisymmetric_member(1.0)
    broken["layers"][1] = {"weight": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], "bias": [0.0, 0.0]}
    p = write_artifact(
        tmp_path,
        nn_artifact(
            feature_names=["f0", "f1"], careers=["alpha", "beta"], members=[broken]
        ),
    )
    with pytest.raises(MatcherModelError):
        load_matcher(p)


def test_output_width_must_match_the_career_count(tmp_path):
    p = write_artifact(
        tmp_path,
        nn_artifact(
            feature_names=["f0", "f1"],
            careers=["alpha", "beta", "gamma"],
            members=[antisymmetric_member(1.0)],
        ),
    )
    with pytest.raises(MatcherModelError):
        load_matcher(p)


def test_an_artifact_with_no_members_is_refused(tmp_path):
    p = write_artifact(
        tmp_path,
        nn_artifact(feature_names=["f0", "f1"], careers=["alpha", "beta"], members=[]),
    )
    with pytest.raises(MatcherModelError):
        load_matcher(p)


def test_a_ragged_weight_matrix_is_refused_as_the_catchable_error(tmp_path):
    """`np.asarray` raises ValueError on ragged input and `load_matcher` catches
    only MatcherModelError — so without translation this artifact would take service
    startup down instead of falling back to the formula."""
    ragged = antisymmetric_member(1.0)
    ragged["layers"][0] = {"weight": [[1.0, 0.0], [0.0]], "bias": [0.0, 0.0]}
    p = write_artifact(
        tmp_path,
        nn_artifact(feature_names=["f0", "f1"], careers=["alpha", "beta"], members=[ragged]),
    )
    with pytest.raises(MatcherModelError):
        load_matcher(p)


def test_non_numeric_weights_are_refused_as_the_catchable_error(tmp_path):
    corrupt = antisymmetric_member(1.0)
    corrupt["layers"][0] = {"weight": [["x", 0.0], [0.0, 1.0]], "bias": [0.0, 0.0]}
    p = write_artifact(
        tmp_path,
        nn_artifact(feature_names=["f0", "f1"], careers=["alpha", "beta"], members=[corrupt]),
    )
    with pytest.raises(MatcherModelError):
        load_matcher(p)


def test_unknown_activation_is_refused_rather_than_assumed(tmp_path):
    p = write_artifact(tmp_path, two_member_artifact(activation="tanh"))
    with pytest.raises(MatcherModelError, match="activation"):
        load_matcher(p)


# ------------------------------------------------------------------ forward pass
def test_forward_pass_reproduces_the_hand_worked_member_probabilities(tmp_path):
    """One member, so the ensemble mean is that member and the expected value is
    sigmoid(2) worked out on paper."""
    p = write_artifact(
        tmp_path,
        nn_artifact(
            feature_names=["f0", "f1"],
            careers=["alpha", "beta"],
            members=[antisymmetric_member(1.0)],
        ),
    )
    probs = load_matcher(p).predict_proba(VECTOR)
    assert probs["alpha"] == pytest.approx(SIGMOID_2)
    assert probs["beta"] == pytest.approx(1 - SIGMOID_2)


def test_serves_the_mean_probability_not_the_mean_logit(tmp_path):
    """The distinction the whole attribution decision rests on. Averaging the two
    members' probabilities gives 0.9314; averaging their LOGITS first and then
    taking the softmax gives 0.9526. They are different functions, and the served
    one is the first."""
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    probs = matcher.predict_proba(VECTOR)
    assert probs["alpha"] == pytest.approx(MEAN_PROBABILITY)
    assert probs["alpha"] != pytest.approx(SIGMOID_3)


def test_probabilities_sum_to_one(tmp_path):
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    assert sum(matcher.predict_proba(VECTOR).values()) == pytest.approx(1.0)


def test_relu_actually_clamps(tmp_path):
    """z = [-2, 1] drives the first hidden unit negative. Without the ReLU the
    logits would be k*(-2 - 1) = -3k; with it they are k*(0 - 1) = -k."""
    matcher = load_matcher(
        write_artifact(
            tmp_path,
            nn_artifact(
                feature_names=["f0", "f1"],
                careers=["alpha", "beta"],
                members=[antisymmetric_member(1.0)],
            ),
        )
    )
    probs = matcher.predict_proba([-2.0, 1.0])
    assert probs["alpha"] == pytest.approx(1 / (1 + math.exp(2.0)))  # softmax([-1, 1])


def test_temperature_divides_the_ensemble_logit(tmp_path):
    """T applies to log(mean probability) — the same place train_models
    `apply_temperature` applies it, since that function takes PROBABILITIES and the
    ensemble's probabilities are the averaged ones."""
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact(temperature=2.0)))
    probs = matcher.predict_proba(VECTOR)
    lo = math.log(MEAN_PROBABILITY) / 2.0
    hi = math.log(1 - MEAN_PROBABILITY) / 2.0
    expected = math.exp(lo) / (math.exp(lo) + math.exp(hi))
    assert probs["alpha"] == pytest.approx(expected)
    # ... and NOT to the mean of the members' logits, which would give a different
    # number entirely.
    assert probs["alpha"] != pytest.approx(1 / (1 + math.exp(-3.0)))


def test_wrong_length_vector_is_rejected(tmp_path):
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    with pytest.raises(MatcherModelError):
        matcher.predict_proba([1.0, 2.0, 3.0])


# ------------------------------------------------------- attribution: the target
def centered_logit(matcher, vector: list[float]) -> dict[str, float]:
    """The quantity attributions must sum to the change in, derived from the
    matcher's FORWARD pass only — an independent route to the same number, since
    the attributions come from a path integral of gradients."""
    probs = matcher.predict_proba(vector)
    logits = {cid: math.log(p) for cid, p in probs.items()}
    mean = sum(logits.values()) / len(logits)
    return {cid: v - mean for cid, v in logits.items()}


def baseline_vector(matcher) -> list[float]:
    """The IG baseline is the scaler mean, i.e. the z = 0 vector."""
    return list(matcher.mean)


def test_attributions_sum_to_the_change_in_the_centered_logit(tmp_path):
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    at_x = centered_logit(matcher, VECTOR)
    at_baseline = centered_logit(matcher, baseline_vector(matcher))
    for cid in ("alpha", "beta"):
        attributed = sum(matcher.contributions(VECTOR, cid).values())
        assert attributed == pytest.approx(at_x[cid] - at_baseline[cid], rel=1e-3)


def test_completeness_is_asserted_on_the_centered_logit_not_the_raw_one(tmp_path):
    """The trap this test exists for: an implementation that skipped the
    across-class centering would still satisfy the UNCENTERED identity, and a test
    written against that identity would pass while the shipped explanation
    described a different quantity.

    The fixture is chosen so the two targets are far apart — the raw logit of
    `alpha` moves by a different amount than its centered logit — so attributions
    summing to the raw change fail here.
    """
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    probs_x = matcher.predict_proba(VECTOR)
    probs_base = matcher.predict_proba(baseline_vector(matcher))
    raw_delta = math.log(probs_x["alpha"]) - math.log(probs_base["alpha"])
    centered_delta = (
        centered_logit(matcher, VECTOR)["alpha"]
        - centered_logit(matcher, baseline_vector(matcher))["alpha"]
    )
    # The fixture must actually discriminate, or the assertion below proves nothing.
    assert abs(raw_delta - centered_delta) > 0.5

    attributed = sum(matcher.contributions(VECTOR, "alpha").values())
    assert attributed == pytest.approx(centered_delta, rel=1e-3)
    assert attributed != pytest.approx(raw_delta, rel=1e-3)


def test_centered_attributions_cancel_across_careers(tmp_path):
    """Centering means a shift shared by every career contributes nothing — the
    same softmax-invariance the linear path relies on."""
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    per_feature = [
        sum(matcher.contributions(VECTOR, cid)[name] for cid in matcher.careers)
        for name in matcher.feature_names
    ]
    assert per_feature == pytest.approx([0.0, 0.0], abs=1e-9)


def test_attribution_keys_are_the_feature_names(tmp_path):
    """Unchanged output shape is what leaves reason_builder untouched."""
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    contributions = matcher.contributions(VECTOR, "alpha")
    assert list(contributions) == matcher.feature_names
    assert all(isinstance(v, float) for v in contributions.values())


def test_a_feature_at_its_baseline_earns_no_attribution(tmp_path):
    """IG attributes the move from the baseline, so a feature sitting on the
    scaler mean has nothing to explain regardless of its gradient."""
    artifact = two_member_artifact(scaler_mean=[0.0, 1.0], scaler_scale=[1.0, 1.0])
    matcher = load_matcher(write_artifact(tmp_path, artifact))
    assert matcher.contributions(VECTOR, "alpha")["f1"] == pytest.approx(0.0, abs=1e-12)


def test_the_gradient_is_the_gradient_of_the_quantity_being_explained(tmp_path):
    """The one seam that separates a wrong model from a coarse integral.

    Completeness alone cannot catch a gradient that is analytically wrong in a way
    the path integral happens to absorb, and the quadrature error is large enough
    here to hide a small mistake. Finite differences of `_explained_logit` are an
    independent derivation of the same derivative, so this pins the chain rule
    through the ensemble mean — the part that is NOT the average of the members.
    """
    matcher = load_matcher(write_artifact(tmp_path, full_size_nn_artifact()))
    z = matcher._scaled([0.35 * ((i * 7) % 11 - 5) for i in range(len(matcher.feature_names))])
    analytic = matcher._ensemble_gradient(z[None, :])[0]

    width = len(matcher.feature_names)
    h = 1e-6
    # One index from each block of the layout, derived rather than hardcoded — the
    # vector is 2*questions + 3*careers wide and both counts move (see CLAUDE.md).
    for j in (0, width // 4, width // 2, width - 1):
        up, down = z.copy(), z.copy()
        up[j] += h
        down[j] -= h
        numeric = (
            matcher._explained_logit(up[None, :])[0]
            - matcher._explained_logit(down[None, :])[0]
        ) / (2 * h)
        assert analytic[:, j] == pytest.approx(numeric, abs=1e-6)


def test_completeness_improves_as_the_step_count_rises(tmp_path):
    """The property that makes an adaptive schedule worth having at all: the
    residual is quadrature error, so it must fall with `m` rather than sit on a
    floor. If it plateaued, doubling would be theatre and the fall-through would be
    hiding a bug rather than a budget.
    """
    matcher = load_matcher(write_artifact(tmp_path, full_size_nn_artifact()))
    z = matcher._scaled([0.35 * ((i * 7) % 11 - 5) for i in range(len(matcher.feature_names))])
    delta = matcher._centered_delta(z)
    errors = [
        float(abs(matcher._centered_ig(z, m).sum(axis=1) - delta).max())
        for m in (32, 128, 512)
    ]
    assert errors[1] < errors[0] / 2
    assert errors[2] < errors[1] / 2


def test_a_realistically_shaped_network_does_not_reach_tolerance_at_the_cap(tmp_path):
    """**The finding this ticket is obliged to record**, pinned so it cannot rot.

    At the shipped trunk shape the integrand has a jump discontinuity at every ReLU
    breakpoint, so a midpoint Riemann sum converges at O(1/m) — measured, not
    assumed, by the test above. The plan's cap of 512 steps therefore lands roughly
    an order of magnitude short of a 1e-3 residual RELATIVE TO THE CENTERED DELTA,
    and the careers it fails hardest on are the near-uniform ones whose delta is
    small. This test asserts the fall-through actually engages, so that if a future
    change makes the cap sufficient, it fails and someone re-reads the record rather
    than discovering the guarantee changed by accident.
    """
    from app.services import matcher_nn

    # Five members and a 64 -> 32 trunk: the shipped shape, and the shape the
    # reproduction record's measurements were taken at.
    matcher = load_matcher(
        write_artifact(tmp_path, full_size_nn_artifact(n_members=5, hidden=(64, 32)))
    )
    vector = [0.35 * ((i * 7) % 11 - 5) for i in range(len(matcher.feature_names))]
    results = [matcher.explain(vector, cid) for cid in matcher.careers]

    assert matcher_nn.IG_MAX_STEPS == 512  # the cap the finding is about
    assert any(not r.converged for r in results)
    for r in results:
        # Whatever the verdict, the ABSOLUTE identity is the one the integral is
        # actually converging on, and it holds to the accuracy the steps bought.
        assert r.absolute_residual < 0.2

    # A career that fails gets silence, not partial numbers.
    failed = next(r for r in results if not r.converged)
    cid = matcher.careers[results.index(failed)]
    assert matcher.contributions(vector, cid) == {}


# ------------------------------------------------------ attribution: the guards
def test_explain_records_the_step_count_and_the_achieved_residual(tmp_path):
    """'A measured guarantee per request, not a hoped-for one' — the measurement
    has to be readable, or the guarantee is a comment."""
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    result = matcher.explain(VECTOR, "alpha")
    assert result.steps >= 32
    assert result.steps <= 512
    assert result.steps & (result.steps - 1) == 0  # a doubling of 32
    assert 0.0 <= result.residual < 1e-3
    assert result.converged


def test_step_count_doubles_until_the_residual_is_met(monkeypatch, tmp_path):
    """Force the starting budget to be too small and the schedule must climb
    rather than serve the residual it happens to land on."""
    from app.services import matcher_nn

    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    monkeypatch.setattr(matcher_nn, "IG_MIN_STEPS", 1)
    _, coarse = matcher._residuals(
        matcher._centered_ig(matcher._scaled(VECTOR), 1)[0],
        float(matcher._centered_delta(matcher._scaled(VECTOR))[0]),
    )
    assert coarse > 1e-3  # a single step really is not good enough here

    result = matcher.explain(VECTOR, "alpha")
    assert result.steps > 1
    assert result.converged
    assert result.residual < coarse


def test_a_career_that_cannot_reach_tolerance_emits_no_attributions(
    monkeypatch, tmp_path
):
    """The fall-through: silence rather than numbers that do not add up. An
    unreachable tolerance stands in for a network the Riemann sum cannot resolve —
    the branch is the same one either way."""
    from app.services import matcher_nn

    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    monkeypatch.setattr(matcher_nn, "IG_REL_TOLERANCE", 0.0)
    result = matcher.explain(VECTOR, "alpha")
    assert not result.converged
    assert result.steps == matcher_nn.IG_MAX_STEPS  # climbed to the cap first
    assert result.contributions  # explain() still reports what it measured
    assert matcher.contributions(VECTOR, "alpha") == {}  # ... but serving does not


def test_unknown_career_is_refused(tmp_path):
    matcher = load_matcher(write_artifact(tmp_path, two_member_artifact()))
    with pytest.raises(MatcherModelError, match="gamma"):
        matcher.contributions(VECTOR, "gamma")


# ------------------------------------------------------------------ end to end
def test_the_matching_service_serves_the_neural_matcher_unchanged(tmp_path):
    """`reason_builder` required no modification, so the response shape a neural
    artifact produces is the shape the linear one produces."""
    from collections import Counter

    from app.repositories.career_repository import CareerCandidate
    from app.services.matching_service import match
    from common.data import load_careers

    matcher = load_matcher(write_artifact(tmp_path, full_size_nn_artifact()))
    candidates = [CareerCandidate(c, 0.5, Counter({"react": 3})) for c in load_careers()]
    answers = {f"q{i}": (i % 4) for i in range(1, 11)}

    with_nn = match(answers, candidates, model=matcher)
    with_formula = match(answers, candidates)
    assert len(with_nn) == 3
    for a, b in zip(with_nn, with_formula):
        assert set(a.keys()) == set(b.keys())
    assert all(r["model_version"] == "test-nn-v0" for r in with_nn)
    assert all(r["reasons"] for r in with_nn)


def test_a_silent_career_still_gets_the_non_model_wording(monkeypatch, tmp_path):
    """The fall-through, end to end: no attributions means no attribution-driven
    sentences, and `reason_builder`'s own fallback sentence instead. The user sees a
    plainer reason, never a missing one."""
    from collections import Counter

    from app.repositories.career_repository import CareerCandidate
    from app.services import matcher_nn
    from app.services.matching_service import match
    from common.data import load_careers

    matcher = load_matcher(write_artifact(tmp_path, full_size_nn_artifact()))
    monkeypatch.setattr(matcher_nn, "IG_REL_TOLERANCE", 0.0)
    candidates = [CareerCandidate(c, 0.5, Counter()) for c in load_careers()]
    recs = match({f"q{i}": (i % 4) for i in range(1, 11)}, candidates, model=matcher)

    assert all(r["reasons"] == ["A direction worth exploring based on your responses"]
               for r in recs)
    assert all(r["model_version"] == "test-nn-v0" for r in recs)
