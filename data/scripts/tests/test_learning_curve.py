"""The learning curve's subsampler, validation rule and Delta-gap contrast.

DEV-96, plan `docs/dev-23-nn-rework-plan.md` Step 2.6. Vocabulary is `CONTEXT.md`'s.

Three properties here are load-bearing rather than bookkeeping, and each of them
would fail silently rather than loudly if it broke:

- **Subsamples are NESTED.** The pre-registered reading of the curve is
  `Delta-gap = gap(232) - gap(80)` computed over "the 80 profiles common to both
  points", and that set only exists if the n=80 subsample is a SUBSET of the n=232
  one. A subsampler that drew independently at each point would still return the
  right sizes, still produce a plausible curve, and quietly make the headline
  quantity a comparison between two disjoint populations.
- **Every subsample keeps at least `CLASS_FLOOR` rows of every class.**
  `dataset_guards.assert_min_class_coverage` runs on the FULL table and cannot see
  these; the curve's own protocol is what has to enforce it. `StratifiedKFold(3)`
  needs three members per class in whatever it is handed, and n=48 is exactly the
  floor times the class count.
- **`NNClassifier(val_size=)` is inert at its default.** `test_variant_registry.py`
  requires the control Variant's predictions to be bit-identical to
  `NNClassifier(random_state=...)`, which is what keeps `small_nn`'s recorded Gate-1
  numbers describing the same estimator. A new constructor argument that perturbed
  the default path would move numbers this whole ticket is measured against.

Run under the hash-pinned training venv (`data/scripts/README.md`; `Scripts/`
rather than `bin/` on Windows). Under the service-test venv this module skips
whole, like `test_nn_model.py`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("torch")

import learning_curve as lc  # noqa: E402


def labels_like_the_real_thing():
    """The real per-career label counts, which are what make the floor bind.

    `game-dev` has exactly 5 labels and `frontend` 47, so the floor is a real
    constraint at every point rather than a formality, and the uniform control curve
    is capped at 5 per class by that same 5. Written as counts rather than read from
    the parquet so the test does not need the dataset to run.
    """
    counts = [47, 18, 17, 16, 15, 15, 15, 14, 13, 12, 11, 11, 9, 8, 6, 5]
    return np.concatenate([np.full(c, i) for i, c in enumerate(counts)])


def test_a_subsample_holds_exactly_n_rows_and_never_fewer_than_the_floor_per_class():
    y = labels_like_the_real_thing()
    for n in lc.CURVE_POINTS:
        idx = lc.class_floored_subsample(y, n)
        assert len(idx) == n, n
        assert len(set(idx.tolist())) == n, f"{n}: duplicate rows"
        counts = np.bincount(y[idx], minlength=16)
        assert counts.min() >= lc.CLASS_FLOOR, (n, counts.tolist())


def test_every_curve_point_is_a_subset_of_every_larger_one():
    """The Delta-gap CI is computed over the profiles common to n=80 and n=232, and
    that set is only the n=80 subsample if the subsamples nest. Checked across every
    pair rather than only the reported one, because a construction that nests for the
    pair the report happens to use and not elsewhere is nesting by luck."""
    y = labels_like_the_real_thing()
    sets = {n: set(lc.class_floored_subsample(y, n).tolist()) for n in lc.CURVE_POINTS}
    for small, large in zip(lc.CURVE_POINTS, lc.CURVE_POINTS[1:]):
        assert sets[small] < sets[large], f"n={small} is not contained in n={large}"
    assert sets[max(lc.CURVE_POINTS)] == set(range(len(y)))


def test_the_balance_confound_matches_the_figures_the_plan_pre_registered():
    """Class-floored subsampling makes the SMALL-n points more balanced, so balance
    and n move together and an observed narrowing could be a balance effect. Plan
    Step 2.6 states the size of that confound in advance -- max:min skew 1.0 at n=48,
    about 3.7 at n=80, 9.4 at n=232 -- so those are an independent source of truth for
    the subsampler rather than numbers read off its own output.
    """
    y = labels_like_the_real_thing()
    skew = {n: lc.class_balance(y, lc.class_floored_subsample(y, n))["skew"]
            for n in lc.CURVE_POINTS}

    assert skew[48] == pytest.approx(1.0), "n=48 is 16 classes x the floor: uniform"
    assert skew[80] == pytest.approx(3.7, abs=0.2)
    assert skew[232] == pytest.approx(9.4, abs=0.05)
    # Monotone in n is the confound itself, stated as a property: every step up in n
    # is a step up in imbalance, which is why the report prints skew beside every gap.
    ordered = [skew[n] for n in lc.CURVE_POINTS]
    assert ordered == sorted(ordered)


def test_the_control_curve_is_perfectly_uniform_and_capped_by_the_rarest_class():
    """The balance-controlled control curve holds balance FIXED while n moves, which
    is the only thing that separates a data-size effect from a balance effect here.
    Its two points are k=4 and k=5 per class; `game-dev`'s 5 labels are what cap it at
    k=5, and that cap is why it is a two-point sanity check rather than a trend."""
    y = labels_like_the_real_thing()
    for k, n in zip(lc.CONTROL_K, lc.CONTROL_POINTS):
        idx = lc.uniform_subsample(y, k)
        counts = np.bincount(y[idx], minlength=16)
        assert len(idx) == n
        assert set(counts.tolist()) == {k}, counts.tolist()
        assert lc.class_balance(y, idx)["skew"] == 1.0

    # Nested for the same reason the main curve is, and inside the full table.
    assert set(lc.uniform_subsample(y, 4).tolist()) < set(lc.uniform_subsample(y, 5).tolist())

    with pytest.raises(ValueError, match="rarest class, which has only 5"):
        lc.uniform_subsample(y, 6)


def test_the_validation_rule_is_one_rule_and_it_binds_at_the_small_points():
    """`n_val = max(n_classes, ceil(0.15 * n_train))`, applied identically at every
    curve point. The `n_classes` arm is not decoration: under 3-fold CV the plain
    15% rule asks for 5 validation rows at n=48 and 8 at n=80, and a stratified split
    of 16 classes cannot produce either.

    A frozen epoch budget was the alternative and plan Step 2.6 rejects it explicitly:
    the optimal epoch count genuinely falls as n falls, so a budget tuned at n=232
    would over-train the small-n points and manufacture the very narrowing the curve
    exists to test for.
    """
    assert lc.validation_size(155, 16) == 24   # n=232: the 15% arm wins
    assert lc.validation_size(116, 16) == 18   # n=174: still the 15% arm
    assert lc.validation_size(77, 16) == 16    # n=116: the class-count arm takes over
    assert lc.validation_size(53, 16) == 16    # n=80
    assert lc.validation_size(32, 16) == 16    # n=48: half the training rows


def test_an_absolute_validation_size_is_inert_at_its_default():
    """`test_variant_registry.py` requires the control Variant to predict identically
    to `NNClassifier(random_state=...)`, which is what keeps `small_nn`'s recorded
    Gate-1 numbers describing the same estimator. This ticket adds a constructor
    argument, so that inertness has to be re-established here rather than assumed --
    bit-identity, not closeness.
    """
    from nn_model import NNClassifier

    X, y = _dataset()
    default = NNClassifier(random_state=42).fit(X, y)
    explicit_none = NNClassifier(random_state=42, val_size=None).fit(X, y)

    assert np.array_equal(explicit_none.predict_proba(X), default.predict_proba(X))


def test_an_absolute_validation_size_lands_on_exactly_that_many_rows():
    """The reason this is an argument rather than a computed `val_fraction`: that
    float is handed to `train_test_split`, which takes `ceil(fraction * n)`, and
    `n_val / n_train * n_train` is not guaranteed to come back on the integer it was
    built from. The estimator records what it actually used, and the curve reports
    that rather than what it requested.
    """
    from nn_model import NNClassifier

    X, y = _dataset(n=140, n_classes=4)
    for requested in (16, 21, 35):
        fitted = NNClassifier(random_state=42, val_size=requested).fit(X, y)
        assert fitted.n_val_ == requested

    # And the default path still reports the fraction it resolved, so both paths
    # answer the same question.
    assert NNClassifier(random_state=42).fit(X, y).n_val_ == 21  # ceil(0.15 * 140)


def test_the_subsample_tie_break_is_counted_and_it_decided_something_real():
    """Two classes with equally many surplus rows produce identical ordering keys, so
    a random draw decides which of them lands inside a curve point. That is an
    arbitrary resolver deciding the membership of a measurement, and DEV-95's review
    established that such a resolver gets counted rather than argued about.

    The count is only worth printing if the resolver actually decided something, so
    that is what is asserted: at every point with a non-empty count, the contested
    rows straddle the cut -- some are in the subsample and some are not -- and they
    come from more than one class, which is the only way their keys could have tied.
    A count of rows that all fell the same side would be decoration.
    """
    y = labels_like_the_real_thing()
    incidence = lc.tie_break_incidence(y)

    # Nothing is decided where nothing is cut: n=48 takes no surplus, n=232 takes all.
    assert incidence[48]["rows_decided_by_tie_break"] == 0
    assert incidence[232]["rows_decided_by_tie_break"] == 0

    for n in lc.CURVE_POINTS:
        contested = set(incidence[n]["contested_rows"])
        assert incidence[n]["rows_decided_by_tie_break"] == len(contested)
        if not contested:
            continue
        inside = contested & set(lc.class_floored_subsample(y, n).tolist())
        assert 0 < len(inside) < len(contested), (
            f"n={n}: the contested group did not straddle the cut, so nothing about "
            "it was decided by the tie-break"
        )
        assert len(set(y[list(contested)].tolist())) > 1, (
            f"n={n}: contested rows are all one class, so their keys cannot have tied"
        )


def _gap_inputs(n_profiles=80, n_seeds=5, seed=7):
    """Long-form (profile, seed) top-2 indicators for four legs, as the curve produces
    them: the NN and one comparator, at the large point and at the small one."""
    rng = np.random.default_rng(seed)
    ids = np.concatenate([np.arange(n_profiles) for _ in range(n_seeds)])
    legs = {k: rng.integers(0, 2, size=len(ids)).astype(float)
            for k in ("nn_large", "comp_large", "nn_small", "comp_small")}
    return ids, legs


def test_delta_gap_is_the_difference_of_the_two_gaps_and_nothing_else():
    """`Delta-gap = gap(232) - gap(80)` with `gap = comparator - NN`, so a NEGATIVE
    delta is narrowing: the comparator's lead over the neural matcher is smaller at
    the larger point.

    It is computed by handing two composite arrays to the pinned
    `sweep_variants.paired_bootstrap`, because that function owns the sampling unit
    (the profile) and averaging inside the unit before differencing is linear -- so
    the contrast survives it exactly. This test is what makes that algebra a
    checked claim rather than a comment: the point estimate must equal the
    difference-of-differences computed directly.
    """
    ids, legs = _gap_inputs()

    result = lc.delta_gap_bootstrap(ids, **legs)

    gap_large = legs["comp_large"].mean() - legs["nn_large"].mean()
    gap_small = legs["comp_small"].mean() - legs["nn_small"].mean()
    assert result["delta"] == pytest.approx(gap_large - gap_small)
    assert result["sampling_unit"] == "profile"
    assert result["n_profiles"] == 80


def test_the_profile_is_still_the_sampling_unit_after_the_contrast():
    """The property a row-resampling implementation cannot satisfy: five identical
    replicate seeds carry no information about profile sampling, so they must not
    narrow the interval at all. `test_paired_bootstrap.py` pins this for the plain
    comparison; the contrast has to inherit it rather than be assumed to.
    """
    ids, legs = _gap_inputs(n_seeds=1)
    one = lc.delta_gap_bootstrap(ids, **legs)

    replicated_ids = np.concatenate([ids] * 5)
    five = lc.delta_gap_bootstrap(
        replicated_ids, **{k: np.concatenate([v] * 5) for k, v in legs.items()}
    )

    assert five["delta"] == pytest.approx(one["delta"])
    assert five["ci_low"] == pytest.approx(one["ci_low"])
    assert five["ci_high"] == pytest.approx(one["ci_high"])


def test_the_verdict_uses_only_the_two_values_the_plan_pre_registered():
    """"Narrowing" iff the CI excludes zero in the narrowing direction; **anything
    else is "flat / inconclusive"**. No trend is claimed from a point-estimate slope,
    which is the rule plan Step 2.6 pre-registered in place of a low-power
    non-overlapping-CIs proxy.

    The case worth pinning is the third one: an interval excluding zero on the
    WIDENING side is still "flat / inconclusive", because a verdict vocabulary
    invented after seeing the data is not a pre-registered rule. It is recorded on a
    separate key so the report can disclose it beside the verdict rather than as it.
    """
    narrowed = {"delta": -0.08, "ci_low": -0.14, "ci_high": -0.02}
    covers_zero = {"delta": -0.08, "ci_low": -0.19, "ci_high": +0.03}
    widened = {"delta": +0.06, "ci_low": +0.01, "ci_high": +0.11}

    assert lc.delta_gap_verdict(narrowed) == "narrowing"
    assert lc.delta_gap_verdict(covers_zero) == "flat / inconclusive"
    assert lc.delta_gap_verdict(widened) == "flat / inconclusive"

    assert {lc.delta_gap_verdict(b) for b in (narrowed, covers_zero, widened)} == {
        "narrowing", "flat / inconclusive"
    }


def test_widening_is_recorded_even_though_it_is_not_a_verdict():
    """It must not vanish into "inconclusive" -- an interval excluding zero on the
    widening side is a real observation, and the report prints it as a disclosure."""
    ids, legs = _gap_inputs()
    # Make the comparator's lead strictly larger at the large point for every row, so
    # the contrast is unambiguously positive and the interval cannot straddle zero.
    legs["comp_large"] = np.ones_like(legs["comp_large"])
    legs["nn_large"] = np.zeros_like(legs["nn_large"])
    legs["comp_small"] = np.zeros_like(legs["comp_small"])
    legs["nn_small"] = np.zeros_like(legs["nn_small"])

    result = lc.delta_gap_bootstrap(ids, **legs)

    assert result["delta"] > 0 and result["ci_low"] > 0
    assert result["widening_excludes_zero"] is True
    assert result["verdict"] == "flat / inconclusive"


def _dataset(n=140, d=12, n_classes=4, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)).astype(np.float32)
    y = np.tile(np.arange(n_classes), n // n_classes)
    X[np.arange(n), y % d] += 2.5  # a signal, so fits are not pure noise
    return X, y
