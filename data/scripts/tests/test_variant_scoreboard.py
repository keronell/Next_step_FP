"""The inner-CV contest records what every grid point scored, not only the winner.

DEV-93 computed a 14-way inner-CV contest 25 times over and kept the argmax alone.
ADR 0006's disqualification clause then fired -- "the shipped model becomes the best
genuinely non-linear Variant" -- and the evidence needed to name that replacement had
already been thrown away. This module pins the out-channel that keeps it.

**The out-channel is additive and that is the property under test here.**
`select_by_inner_cv` has six call sites, one of which
(`test_residual_matcher.py::test_selection_inherits_the_folds_C_and_records_one_alpha_per_outer_fold`)
asserts on its return value directly, so a changed return type would silently change
what four other callers receive. The scores leave through a parameter the existing
callers do not pass.

Run under the hash-pinned training venv (`data/scripts/README.md`; `Scripts/` rather
than `bin/` on Windows). Skips whole under the service-test venv.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("torch")

from sweep_variants import VARIANTS, select_variant  # noqa: E402
from train_models import INNER_SPLITS, select_by_inner_cv  # noqa: E402


class _Oracle:
    """Reads the label out of column 0 and puts all its mass there."""

    def predict_proba(self, X):
        probs = np.zeros((len(X), N_CLASSES))
        probs[np.arange(len(X)), X[:, 0].astype(int)] = 1.0
        return probs


class _Constant:
    """Uniform over every class, so `argsort(-probs)[:, :2]` is always {0, 1}."""

    def predict_proba(self, X):
        return np.full((len(X), N_CLASSES), 1.0 / N_CLASSES)


N_CLASSES = 4
_ESTIMATORS = {"oracle": _Oracle, "constant": _Constant}


def _fit(params, Xtr, ytr):
    return _ESTIMATORS[params]()


def make_dataset(n=120, d=6, seed=0):
    """Column 0 carries the label, so `_Oracle` is exactly right by construction and
    its inner-CV score is 1.0 without depending on anything the code under test does."""
    rng = np.random.default_rng(seed)
    y = np.tile(np.arange(N_CLASSES), n // N_CLASSES)
    X = rng.normal(size=(n, d))
    X[:, 0] = y
    return X, y


def test_the_score_of_every_grid_point_is_recorded_in_grid_order():
    """The vector DEV-93 discarded. Both expected values come from the estimators'
    definitions rather than from re-running the selection: `_Oracle` ranks the true
    class first for every row, and `_Constant` ties every class so the top-2 set is
    always {0, 1} -- a hit exactly for the rows whose label is 0 or 1."""
    X, y = make_dataset()
    tr = np.arange(0, 100)
    scores = []

    select_by_inner_cv(X, y, tr, ["oracle", "constant"], _fit, scores_out=scores)

    assert [name for name, _ in scores] == ["oracle", "constant"]
    assert scores[0][1] == 1.0
    assert scores[1][1] == pytest.approx(float(np.mean(y[tr] <= 1)), abs=0.05)


def test_the_recorded_scores_describe_the_contest_that_produced_the_pick():
    """An out-channel filled from a second, differently-configured run of the contest
    would be worse than no channel at all: the substitution ADR 0006 owes is chosen by
    reading these numbers, so the winner must be their argmax and not merely near it."""
    X, y = make_dataset()
    tr = np.arange(0, 100)
    scores = []

    chosen = select_by_inner_cv(X, y, tr, ["constant", "oracle"], _fit, scores_out=scores)

    assert chosen == max(scores, key=lambda item: item[1])[0]


def test_passing_no_channel_leaves_the_existing_callers_answer_untouched():
    """The additivity property, stated as an equality rather than trusted.

    Four of the six call sites take the return value alone, and one test asserts on it
    directly against an inherited `C`. Instrumenting the function must not move any of
    them, including through the RNG: the grid is walked in the same order and each
    point is fitted the same number of times either way."""
    X, y = make_dataset()
    tr = np.arange(0, 100)

    without = select_by_inner_cv(X, y, tr, ["constant", "oracle"], _fit)
    with_channel = select_by_inner_cv(
        X, y, tr, ["constant", "oracle"], _fit, scores_out=[]
    )

    assert without == with_channel == "oracle"


def test_the_channel_carries_one_score_per_grid_point_per_call():
    """A channel that accumulated across calls would silently double-count when the
    sweep records one vector per outer fold, and the per-fold ranking would then be
    read off a vector containing another fold's numbers."""
    X, y = make_dataset()
    scores = []

    select_by_inner_cv(X, y, np.arange(0, 100), ["oracle", "constant"], _fit,
                       scores_out=scores)

    assert len(scores) == 2
    assert INNER_SPLITS == 3, (
        "the score is a MEAN over inner splits, not one entry per split -- if the "
        "inner-split count changes this test's premise needs re-reading"
    )


# ------------------------------------------------- the 14-way contest's own vector

# The real registry makes every test here a minute long, and this module is about the
# channel rather than about which Variant wins. Three cheap ones, as in
# `test_variant_selection.py`.
CHEAP = {
    name: VARIANTS[name]
    for name in ("A1_84_16_16", "A2_84_32_16", "C1_full_batch")
}


def real_dataset(n=120, d=10, n_classes=4, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)).astype(np.float32)
    y = np.tile(np.arange(n_classes), n // n_classes)
    X[np.arange(n), y % d] += 2.5
    return X, y


def test_the_contest_reports_what_each_variant_scored_not_only_which_one_won():
    """The evidence ADR 0006's substitution needs: every Variant's inner-CV score on
    the fold, so "the best genuinely non-linear Variant" is a number to read rather
    than an inference from a selection count of zero."""
    X, y = real_dataset()
    tr = np.arange(0, 80)
    scores = {}

    chosen, _ = select_variant(X, y, tr, random_state=42, variants=CHEAP, scores_out=scores)

    assert set(scores) == set(CHEAP)
    assert all(0.0 <= s <= 1.0 for s in scores.values())
    assert scores[chosen] == max(scores.values())


def test_the_contest_answer_does_not_depend_on_whether_scores_are_collected():
    """`run_one_seed` calls this on every outer fold of every seed, so a channel that
    perturbed the contest would re-decide Round 1 while claiming to describe it."""
    X, y = real_dataset()
    tr = np.arange(0, 80)

    without = select_variant(X, y, tr, random_state=42, variants=CHEAP)
    with_channel = select_variant(X, y, tr, random_state=42, variants=CHEAP, scores_out={})

    assert without == with_channel
