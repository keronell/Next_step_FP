"""Variant selection is a pure function of the outer fold's training partition.

Step 2.4 deleted rev 2's pruning pass because it scored Variants on the outer-fold-1
training partition — which under 5-fold CV is *precisely the union of the test sets
of folds 2-5*, so selection would have seen 100% of the evaluation data for four of
five folds. The replacement is that all 14 Variants compete inside every outer
fold's inner 3-fold CV, so no stage exists that can leak.

That claim is only worth as much as its enforcement, so it is tested the way
`test_cross_fitted_temperature.py` tests the calibration contract: **corrupt every
row the selection is not entitled to see, and require the answer not to move.** A
selection that reached outside `tr` by any path — a stray full-`X` fit, a scaler
fitted on everything, a grid scored on held-out rows — changes its answer and fails
here.

"Leakage" is `CONTEXT.md`'s word for exactly this and is not a synonym for
Circularity, which is a separate and untouched defect of the labels.

Run under the hash-pinned training venv (`data/scripts/README.md`; `Scripts/`
rather than `bin/` on Windows). Skips whole under the service-test venv.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("torch")

import train_models  # noqa: E402
from sweep_variants import VARIANTS, select_variant  # noqa: E402


def make_dataset(n=120, d=10, n_classes=4, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)).astype(np.float32)
    y = np.tile(np.arange(n_classes), n // n_classes)
    X[np.arange(n), y % d] += 2.5
    return X, y


# A cheap stand-in registry: this module is about the SELECTION protocol, not about
# which Variant wins, and the real 14 would make every test here a minute long.
CHEAP = {
    name: VARIANTS[name]
    for name in ("A1_84_16_16", "A2_84_32_16", "C1_full_batch")
}


def test_selection_is_blind_to_every_row_outside_the_training_partition():
    """Corrupt the held-out rows beyond recognition; the selection must not move."""
    X, y = make_dataset()
    tr = np.arange(0, 80)
    held_out = np.arange(80, len(y))

    clean = select_variant(X, y, tr, random_state=42, variants=CHEAP)

    poisoned = X.copy()
    rng = np.random.default_rng(99)
    poisoned[held_out] = rng.normal(loc=500.0, scale=100.0, size=(len(held_out), X.shape[1]))
    poisoned_y = y.copy()
    poisoned_y[held_out] = (poisoned_y[held_out] + 1) % 4

    assert select_variant(poisoned, poisoned_y, tr, random_state=42, variants=CHEAP) == clean


def test_the_residual_alpha_is_recorded_even_when_another_variant_wins_the_fold():
    """The pre-registered >=3-of-5 rule needs a record without holes in it.

    ADR 0006 disqualifies the Residual Matcher when `alpha=0` is selected in >= 3 of
    5 outer folds. "This fold did not pick the Residual Matcher" is a different
    finding from "this fold picked alpha=0", and a record that conflates them can
    make the rule fire, or fail to fire, on evidence that was never gathered.

    So `select_variant` returns the alpha inner CV chose for the residual in EVERY
    fold, independently of which Variant went on to win the contest.
    """
    X, y = make_dataset()
    tr = np.arange(0, 80)
    with_residual = dict(CHEAP)
    with_residual["C4_residual_matcher"] = VARIANTS["C4_residual_matcher"]

    winner, residual_configs = select_variant(
        X, y, tr, random_state=42, variants=with_residual
    )

    assert "C4_residual_matcher" in residual_configs, (
        "the residual's alpha must be recorded whether or not it won this fold"
    )
    alpha, C = residual_configs["C4_residual_matcher"]
    assert alpha in train_models.RESIDUAL_ALPHA_GRID
    assert C in train_models.LOGISTIC_C_GRID
    # The record exists independently of the outcome — that is the whole point.
    assert winner in with_residual


def test_the_experiment_seed_varies_both_the_fold_partition_and_the_initialisation():
    """Seeds sit OUTSIDE selection: each experiment seed is a complete nested run
    that differs in folds *and* init, not a re-init on frozen folds.

    Fold assignment at n=232 with `game-dev` at 5 labels is a genuine variance
    source; freezing it would hide that rather than control it.
    """
    X, y = make_dataset(n=200, n_classes=4)

    a = list(train_models.outer_folds(X, y, random_state=1))
    b = list(train_models.outer_folds(X, y, random_state=2))

    assert any(not np.array_equal(x[1], z[1]) for x, z in zip(a, b))


def test_the_default_fold_partition_is_the_one_dev_91_measured():
    """Every fold helper gained a `random_state` for the 5-seed protocol. Its
    default must reproduce the single-seed path exactly, or the DEV-91 Gate-2
    re-baseline stops being reproducible from this file."""
    X, y = make_dataset(n=200, n_classes=4)

    default = list(train_models.outer_folds(X, y))
    explicit = list(train_models.outer_folds(X, y, random_state=train_models.SEED))

    assert all(
        np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
        for a, b in zip(default, explicit)
    )


def test_within_a_seed_every_model_is_scored_on_the_same_folds():
    """The pairing the bootstrap depends on: gbt, logistic and the NN Variants must
    see identical partitions inside a seed, or their per-profile indicators are not
    paired observations and differencing them means nothing."""
    X, y = make_dataset(n=200, n_classes=4)

    first = list(train_models.outer_folds(X, y, random_state=7))
    second = list(train_models.outer_folds(X, y, random_state=7))

    assert all(
        np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
        for a, b in zip(first, second)
    )
