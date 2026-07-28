"""The leakage contract of the Gate-2 calibration temperature (plan Step 4.2).

`temperature_scale()` used to fit one temperature on the pooled out-of-fold
predictions and then ECE was scored on those same predictions. That is Leakage in
the strict sense `CONTEXT.md` reserves the word for — data used to score a model
influenced that model's fitting — and it is *differential*: a worse-calibrated
model gains more from fitting T on its own evaluation data. Since scaled ECE is
the Gate-2 tiebreak, the bias could flip a winner. ADR 0004 records the decision.

What these tests hold is the property, not the implementation. The load-bearing
one is `test_the_per_fold_temperature_is_blind_to_the_rows_it_will_score`: it
corrupts the outer test rows beyond recognition and requires every per-fold
temperature to come back bit-identical. Any future refactor that quietly returns
to fitting T on the pooled OOF — the single most natural-looking simplification
here, since it is three lines shorter — fails it.

Run from repo root with the TRAINING venv (`Scripts/` replaces `bin/` on Windows,
as everywhere in data/scripts/README.md):

    data/venv-training/bin/python -m pytest data/scripts/tests -q

Under the service-test venv this module skips whole, like `test_nn_model.py`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("torch")
pytest.importorskip("lightgbm")

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from train_models import (  # noqa: E402
    INNER_SPLITS,
    N_FOLDS,
    TEMPERATURE_GRID,
    apply_temperature,
    cross_fitted_oof,
    fit_temperature,
    nll,
    temperature_scale,
)


def make_dataset(n_rows: int = 150, n_features: int = 10, n_classes: int = 5, seed: int = 0):
    """A small, class-balanced, learnable table — deliberately not the real feature
    parquet: these tests are about the fitting protocol, not about the dataset."""
    rng = np.random.default_rng(seed)
    y = np.repeat(np.arange(n_classes), n_rows // n_classes)
    centers = rng.normal(size=(n_classes, n_features)) * 1.5
    X = centers[y] + rng.normal(size=(len(y), n_features)) * 2.0
    return X.astype(np.float64), y


def logistic_fit_predict(config, train_idx, predict_idx, X, y):
    """The `fit_predict` shape `cross_fitted_oof` drives: train on `train_idx`,
    predict on `predict_idx`, both absolute indices into X."""
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=config or 1.0, max_iter=2000, random_state=0),
    ).fit(X[train_idx], y[train_idx])
    return model.predict_proba(X[predict_idx])


# ---------------------------------------------------------------- the primitives

def test_applying_a_temperature_of_one_changes_nothing():
    """T=1.0 must be inert. The shipped artifact carries 1.0 today and DEV-88 made
    the serving path divide logits by it, so this is the property that made that
    change provably safe to land early."""
    rng = np.random.default_rng(0)
    probs = rng.dirichlet(np.ones(6), size=40)
    assert np.allclose(apply_temperature(probs, 1.0), probs, atol=1e-12)


def test_a_higher_temperature_softens_and_a_lower_one_sharpens():
    """Direction check. A temperature that sharpened when it should soften would
    still produce a plausible-looking ECE, so the sign is worth pinning."""
    rng = np.random.default_rng(1)
    probs = rng.dirichlet(np.ones(6) * 0.3, size=40)  # deliberately peaked
    peak = probs.max(axis=1)
    assert (apply_temperature(probs, 2.0).max(axis=1) < peak).all()
    assert (apply_temperature(probs, 0.5).max(axis=1) > peak).all()


def test_fit_temperature_recovers_a_known_distortion():
    """Guards the grid search itself — otherwise every temperature below is a
    number nobody can interpret.

    The labels are drawn FROM the probabilities, which is what makes `p` calibrated
    by construction rather than merely plausible: a temperature fitted on it must
    come back at 1.0, and one fitted on a copy sharpened by 0.5 must come back at
    ~2.0 to undo exactly that.
    """
    rng = np.random.default_rng(2)
    n, k = 4000, 4
    logits = rng.normal(size=(n, k))
    p = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    y = np.array([rng.choice(k, p=p[i]) for i in range(n)])

    assert fit_temperature(p, y) == pytest.approx(1.0, abs=0.2)
    assert fit_temperature(apply_temperature(p, 0.5), y) == pytest.approx(2.0, abs=0.3)


def test_temperature_scale_agrees_with_fit_then_apply():
    """One definition, two callers: `temperature_scale` is the deployment path
    (best estimate from the full pool) and `fit_temperature`/`apply_temperature`
    are the cross-fitted reporting path. They must not drift apart."""
    rng = np.random.default_rng(3)
    n, k = 200, 5
    y = rng.integers(0, k, size=n)
    probs = rng.dirichlet(np.ones(k) * 0.5, size=n)
    scaled, t = temperature_scale(probs, y)
    assert scaled == pytest.approx(apply_temperature(probs, t))
    assert t == pytest.approx(fit_temperature(probs, y))


# ------------------------------------------------------- the leakage contract

def test_the_per_fold_temperature_is_blind_to_the_rows_it_will_score():
    """THE regression test for ADR 0004.

    Corrupt one fold's held-out rows beyond recognition and require that fold's
    temperature back bit-identical — then repeat for all five. A temperature fitted
    on the pooled OOF, which includes predictions made on those rows, cannot survive
    this; one fitted on inner-OOF predictions drawn only from the training partition
    is mathematically independent of them. (Verified to have teeth: against a leaky
    reimplementation, all 5 of 5 fold temperatures move.)

    Two things this test has to get right, both of which it got wrong first:

    - `y` is left alone. It drives the stratified fold assignment, so corrupting it
      would change the partition and the comparison would be meaningless.
    - Exactly ONE fold's test rows are corrupted per run, and only that fold's
      temperature is asserted on. Corrupting every fold's test rows at once
      corrupts every row, and an affine corruption of every row is erased by the
      `StandardScaler` — a vacuous pass. Fold k's test rows are also folds
      1..5-except-k's *training* rows, so the other four temperatures are supposed
      to move.
    """
    X, y = make_dataset()
    rng = np.random.default_rng(99)

    def run(features):
        return cross_fitted_oof(
            features, y, n_classes=len(np.unique(y)),
            fit_predict=lambda c, tr, pr: logistic_fit_predict(c, tr, pr, features, y),
        )

    oof_raw_clean, _, temps_clean, _ = run(X)

    for k, (_, te) in enumerate(_outer_splits(X, y)):
        corrupted = X.copy()
        corrupted[te] = rng.normal(size=(len(te), X.shape[1])) * 50.0
        oof_raw_dirty, _, temps_dirty, _ = run(corrupted)

        assert temps_dirty[k] == temps_clean[k], (
            f"fold {k}'s temperature moved when only fold {k}'s TEST rows changed — "
            "it is being fitted on data it will score (ADR 0004)"
        )
        # Guard against passing vacuously: the corruption must actually have
        # reached the predictions this fold scores, or the assertion above is
        # invariance to something that was never an input.
        assert not np.allclose(oof_raw_dirty[te], oof_raw_clean[te]), (
            f"fold {k}'s corruption never reached the model — the invariance is vacuous"
        )


def test_the_temperature_fit_never_trains_or_predicts_on_an_outer_test_row():
    """The structural complement of the invariance test above. Every fit made while
    a fold's temperature is being estimated must draw both its training and its
    prediction rows from that fold's training partition."""
    X, y = make_dataset()
    calls: list[tuple[np.ndarray, np.ndarray]] = []

    def spy(config, train_idx, predict_idx):
        calls.append((np.asarray(train_idx), np.asarray(predict_idx)))
        return logistic_fit_predict(config, train_idx, predict_idx, X, y)

    cross_fitted_oof(X, y, n_classes=len(np.unique(y)), fit_predict=spy)

    # Per outer fold: INNER_SPLITS calls to estimate T, then one call that scores
    # the held-out rows. The scoring calls are the last of each group; identify
    # them by the only thing that distinguishes them — they are the calls whose
    # prediction rows are NOT a subset of their own fold's training partition.
    fold_train = [set(tr.tolist()) for tr, _ in _outer_splits(X, y)]
    scoring_calls, temperature_calls = 0, 0
    for train_idx, predict_idx in calls:
        owning_fold = next(
            (i for i, tr in enumerate(fold_train) if set(train_idx.tolist()) <= tr), None
        )
        assert owning_fold is not None, (
            "a fit drew training rows from outside every outer training partition"
        )
        if set(predict_idx.tolist()) <= fold_train[owning_fold]:
            temperature_calls += 1  # entirely inside the partition
            continue
        scoring_calls += 1
        assert set(predict_idx.tolist()) == set(range(len(y))) - fold_train[owning_fold], (
            "the scoring fit predicted on something other than exactly its held-out rows"
        )
    assert scoring_calls == N_FOLDS
    # Both counts, or the test passes for an implementation that skips the
    # cross-fit entirely: with zero inner fits every call would be a scoring call
    # and the assertion above would still hold.
    assert temperature_calls == N_FOLDS * INNER_SPLITS


def test_the_calibrated_oof_is_the_raw_oof_with_that_folds_temperature():
    """Ties the two returned matrices together. Reporting raw and cross-fitted ECE
    side by side is only meaningful if the second is exactly the first rescaled."""
    X, y = make_dataset()
    oof_raw, oof_cal, temps, _ = cross_fitted_oof(
        X, y, n_classes=len(np.unique(y)),
        fit_predict=lambda c, tr, pr: logistic_fit_predict(c, tr, pr, X, y),
    )
    assert len(temps) == N_FOLDS
    for (_, te), t in zip(_outer_splits(X, y), temps):
        assert oof_cal[te] == pytest.approx(apply_temperature(oof_raw[te], t))


def test_selection_runs_once_per_outer_fold_and_only_sees_training_rows():
    """The plan's pseudocode opens with `config = select_by_inner_cv(tr)`. That step
    is real for the two nested-selection models and a no-op for the other two, so
    the driver must support both — and when it is used, it must be handed the
    training partition and nothing else."""
    X, y = make_dataset()
    seen: list[np.ndarray] = []

    def select(train_idx):
        seen.append(np.asarray(train_idx))
        return 0.25

    _, _, _, chosen = cross_fitted_oof(
        X, y, n_classes=len(np.unique(y)),
        fit_predict=lambda c, tr, pr: logistic_fit_predict(c, tr, pr, X, y),
        select_config=select,
    )
    assert chosen == [0.25] * N_FOLDS
    for train_idx, (tr, _) in zip(seen, _outer_splits(X, y)):
        assert np.array_equal(train_idx, tr)


def test_a_temperature_fitted_on_a_pool_is_unbeatable_on_that_pool():
    """The defect, stated as the law it actually is — and only that far.

    `fit_temperature` returns the grid argmin, so within the family of **constant**
    temperatures nothing beats a pool-fitted T on the rows it was fitted on. That is
    exactly what makes the old protocol's ECE a fitted minimum rather than a
    measurement, and it is the whole of the guarantee.

    It is deliberately NOT stated as "the legacy number is larger/smaller than the
    cross-fitted one", in ECE or in NLL. Cross-fitting changes two things at once:
    it removes the leak, and it widens the family from one global constant to five
    per-fold constants, which can absorb fold-specific miscalibration a single
    constant cannot. On the real Gate-2 data that second effect wins often enough
    that cross-fitted ECE is lower for three of four models and cross-fitted NLL is
    lower for `logistic_tuned`.

    Two earlier drafts of this test asserted a direction — first in ECE, then in
    NLL — and both passed here by luck of the synthetic data while being false on
    the real run. Hence the narrower claim.
    """
    X, y = make_dataset(n_rows=200, n_classes=5, seed=9)
    oof_raw, _, _, _ = cross_fitted_oof(
        X, y, n_classes=len(np.unique(y)),
        fit_predict=lambda c, tr, pr: logistic_fit_predict(c, tr, pr, X, y),
    )
    pooled, t_pooled = temperature_scale(oof_raw, y)  # fitted on the rows it scores
    best = nll(pooled, y)
    for t in TEMPERATURE_GRID:
        assert best <= nll(apply_temperature(oof_raw, t), y) + 1e-12, (
            f"T={t_pooled} was fitted on these rows but T={t} scores lower on them — "
            "fit_temperature is not returning the argmin"
        )


# ---------------------------------------------------------------- helpers

def _outer_splits(X, y):
    """The exact outer partition `cross_fitted_oof` uses, so a test can name the
    held-out rows of each fold without duplicating the splitter's configuration."""
    from train_models import outer_folds

    return list(outer_folds(X, y))
