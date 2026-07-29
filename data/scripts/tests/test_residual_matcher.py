"""The Residual Matcher's contract (plan Step 2.3, ADR 0003, DEV-92).

`logits = frozen_logistic_logits + alpha * MLP(x)`, summed before the softmax, with
`alpha` a hyperparameter selected by inner CV rather than a learned scalar. Three
of the properties below are the ones a plausible-looking refactor takes away
silently, so each is pinned by a test that fails loudly:

- **At `alpha = 0` it is *exactly* logistic regression** — bit-identical to
  sklearn's `predict_proba`, not merely close. This is the ticket's standalone
  acceptance check. "Close" is precisely the tolerance under which a residual that
  quietly perturbs the base would still pass, and the whole selection safeguard in
  ADR 0003 is that inner CV can always retreat to the Incumbent exactly.
- **The frozen base is refit on whichever partition the MLP trains on** — the
  inner-training subset when inside inner CV, never the whole outer-training
  partition. The plan calls this the single easiest thing to get subtly wrong, and
  getting it wrong is Leakage in the sense `CONTEXT.md` reserves the word for.
- **`alpha` is a hyperparameter.** A learnable alpha initialised at zero is pushed
  off zero immediately because moving it reduces training loss, which reproduces
  the retracted "never worse than logistic" claim with extra steps. The test states
  this as parameter *count*: the Residual Matcher must train no parameter a plain
  `NNClassifier` of the same shape does not.

Run from repo root with the TRAINING venv (`Scripts/` replaces `bin/` on Windows,
as everywhere in data/scripts/README.md):

    data/venv-training/bin/python -m pytest data/scripts/tests -q

Under the service-test venv this module skips whole, like `test_nn_model.py` and
`test_cross_fitted_temperature.py`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

np = pytest.importorskip("numpy")
pytest.importorskip("torch")
pytest.importorskip("sklearn")
pytest.importorskip("lightgbm")

from sklearn.model_selection import StratifiedKFold  # noqa: E402

import train_models  # noqa: E402
from evaluate_matchers import assert_deterministic  # noqa: E402
from nn_model import NNClassifier, ResidualMatcher  # noqa: E402
from train_models import (  # noqa: E402
    INNER_SPLITS,
    LOGISTIC_C_GRID,
    N_FOLDS,
    RESIDUAL_ALPHA_GRID,
    SEED,
    alpha_zero_verdict,
    cross_fitted_oof,
    fit_logistic,
    fit_residual,
    outer_folds,
    select_by_inner_cv,
    select_residual_config,
)

# Small enough that the whole module runs in seconds, large enough that the MLP
# branch actually moves the logits. These are contract tests, not measurements —
# no number produced here is a metric.
FAST = {"hidden_sizes": (8,), "max_epochs": 15}
C = 1.0


def make_dataset(n_rows: int = 90, n_features: int = 12, n_classes: int = 6, seed: int = 0):
    """A small, class-balanced, learnable table — deliberately not the real feature
    parquet: these tests are about the estimator's contract, not about the dataset."""
    rng = np.random.default_rng(seed)
    y = np.repeat(np.arange(n_classes), n_rows // n_classes)
    centers = rng.normal(size=(n_classes, n_features)) * 2.0
    X = centers[y] + rng.normal(size=(len(y), n_features))
    return X.astype(np.float64), y


def residual(alpha, random_state=42, **kw):
    return ResidualMatcher(random_state=random_state, alpha=alpha, logistic_C=C, **FAST, **kw)


# ------------------------------------------------- alpha = 0 IS logistic regression

def test_at_alpha_zero_it_reproduces_the_incumbents_predictions_exactly():
    """THE acceptance check for this ticket.

    `fit_logistic` is the Incumbent's own construction site, so this asserts the
    identity against the model the residual is supposed to collapse to, not against
    a lookalike rebuilt in the test. Bit-identical, because `np.allclose` would
    still pass for a residual that perturbs the base by a hair — and a safeguard
    that only approximately retreats to the Incumbent is not the safeguard ADR 0003
    describes.

    It has teeth against the obvious alternative implementation — taking
    `log(base.predict_proba(X))` as the base logits — and that is not claimed here
    but held one test below, by
    `test_taking_log_probabilities_as_the_base_logits_would_lose_the_identity`.
    """
    X, y = make_dataset()
    model = residual(0.0).fit(X, y)
    expected = fit_logistic(C, X, y).predict_proba(X)
    assert np.array_equal(model.predict_proba(X), expected)


def test_at_alpha_zero_it_returns_its_own_frozen_bases_probabilities():
    """The same identity stated against the fitted base the model carries, which is
    what makes it a property of the forward pass rather than of the fitting. It
    holds because the base branch contributes `decision_function` values and the
    residual applies the same softmax sklearn's `predict_proba` applies to them."""
    X, y = make_dataset()
    model = residual(0.0).fit(X, y)
    assert np.array_equal(model.predict_proba(X), model.base_.predict_proba(X))


def test_a_nonzero_alpha_moves_the_predictions_off_the_logistic_ones():
    """Guards both tests above from passing for the wrong reason. A residual that
    dropped the MLP term entirely — or scaled it to nothing — would satisfy the
    alpha=0 identity trivially and be worthless at every other grid point."""
    X, y = make_dataset()
    base = residual(0.0).fit(X, y).predict_proba(X)
    for alpha in (a for a in RESIDUAL_ALPHA_GRID if a != 0.0):
        assert not np.allclose(residual(alpha).fit(X, y).predict_proba(X), base), (
            f"alpha={alpha} produced the logistic predictions — the MLP branch is inert"
        )


def test_taking_log_probabilities_as_the_base_logits_would_lose_the_identity():
    """The mutant that motivates the implementation, held as a property instead of
    asserted in a docstring.

    `softmax(log(p))` is `p` mathematically — softmax is shift-invariant, so
    log-probabilities are as valid a set of base logits as decision values. The
    exponential round-trip is what costs the last bits. This test is the evidence
    for ADR 0003's "Observed on implementation" note, and it fails the day some
    sklearn or numpy change makes the round-trip exact, at which point that note
    should be rewritten rather than quietly left standing.
    """
    from sklearn.utils.extmath import softmax

    X, y = make_dataset()
    expected = fit_logistic(C, X, y).predict_proba(X)
    via_log_probabilities = softmax(np.log(np.clip(expected, 1e-12, 1.0)), copy=True)

    assert np.allclose(via_log_probabilities, expected)
    assert not np.array_equal(via_log_probabilities, expected)


def test_at_alpha_zero_the_loss_carries_no_gradient_into_the_mlp():
    """Why `predict_proba` needs no branch on alpha, and why training the MLP at
    alpha=0 anyway is nearly free: the loss cannot reach the MLP's parameters at
    all, so the validation loss is constant and early stopping ends the fit after
    one patience window."""
    import torch

    X, y = make_dataset()
    model = residual(0.0).fit(X, y)

    Xs = (X.astype(np.float32) - model.mean_) / model.scale_
    model.model_.train(True)
    logits = (torch.tensor(model.base_.decision_function(X), dtype=torch.float32)
              + model.alpha * model.model_(torch.tensor(Xs)))
    torch.nn.functional.cross_entropy(logits, torch.tensor(y)).backward()

    assert max(float(p.grad.abs().max()) for p in model.model_.parameters()) == 0.0


def test_the_alpha_grid_is_the_pre_registered_one():
    """ADR 0003 fixes the grid at {0, 0.25, 0.5, 1.0}. Widening it later is a
    protocol change, not a tuning tweak, so it should not pass unremarked."""
    assert RESIDUAL_ALPHA_GRID == (0.0, 0.25, 0.5, 1.0)


# ------------------------------------------------- the frozen base's fitting rules

def test_the_frozen_base_is_refit_on_whichever_partition_the_mlp_trains_on():
    """The leak this ticket is most likely to introduce, stated as an equality and
    an inequality.

    Fitted on a subset, the base must be the logistic fit of *that subset* and must
    NOT be the logistic fit of the full table. A refactor that hoists the base fit
    up to the outer-training partition — the natural-looking optimisation, since it
    would be fitted once per fold instead of once per inner split — fails the second
    assertion. `alpha` is 1.0 so the MLP branch trains as hard as it ever does,
    which also makes this a check that training never moves the frozen branch.
    """
    X, y = make_dataset()
    subset = np.arange(0, len(y), 2)  # every other row: stratified by construction

    model = residual(1.0).fit(X[subset], y[subset])
    on_subset = fit_logistic(C, X[subset], y[subset]).decision_function(X)
    on_everything = fit_logistic(C, X, y).decision_function(X)

    assert np.array_equal(model.base_.decision_function(X), on_subset)
    assert not np.allclose(on_subset, on_everything), (
        "the two partitions produce the same logistic fit, so the assertion above "
        "cannot distinguish them — the test is vacuous"
    )


def test_the_base_ignores_random_state_so_it_is_a_function_of_C_and_the_partition():
    """Why the paired comparison in ADR 0003 is exact: the frozen branch is the
    Incumbent's fit on that partition, and the experiment seed the sweep varies
    reaches only the MLP. lbfgs does not consume `random_state`; if a future solver
    change made it do so, the base would drift with the seed and "exactly the
    Incumbent's configuration" would quietly stop being true."""
    X, y = make_dataset()
    a = residual(0.5, random_state=42).fit(X, y)
    b = residual(0.5, random_state=7).fit(X, y)
    assert np.array_equal(a.base_.decision_function(X), b.base_.decision_function(X))
    assert not np.array_equal(a.predict_proba(X), b.predict_proba(X)), (
        "the seed reached nothing at all — the MLP branch is not being trained"
    )


def test_a_binary_problem_is_refused_rather_than_silently_approximated():
    """sklearn's `predict_proba` takes a sigmoid path, not a softmax one, at two
    classes — so the alpha=0 identity would not hold and the additive-logit form
    would be scoring something other than what it claims. 16 careers means this
    cannot arise on the real data; it must still fail loudly rather than quietly."""
    X, y = make_dataset(n_rows=60, n_classes=2)
    with pytest.raises(ValueError, match="two classes|multiclass"):
        residual(0.5).fit(X, y)


# ------------------------------------------------- alpha is not a learned parameter

def test_the_residual_trains_no_parameter_a_plain_mlp_does_not():
    """`alpha` is a hyperparameter and the linear branch is frozen — together that
    means the Residual Matcher's trainable parameter set is exactly the MLP's.

    A learnable gate would add one scalar; an unfrozen linear branch would add a
    (d_in x n_classes) block plus biases. Counting parameters catches both, and
    catches them whatever they end up being called."""
    X, y = make_dataset()
    res = residual(0.5).fit(X, y)
    plain = NNClassifier(random_state=42, **FAST).fit(X, y)
    assert (sum(p.numel() for p in res.model_.parameters())
            == sum(p.numel() for p in plain.model_.parameters()))


def test_fitting_never_moves_alpha():
    """The complement of the count above: nothing rewrites the hyperparameter in
    place either. The per-fold alpha choices are what the pre-registered
    >=3-of-5 rule is read from, so a fitted alpha that had drifted off its selected
    value would make that verdict describe a model nobody trained."""
    X, y = make_dataset()
    model = residual(0.25).fit(X, y)
    assert model.alpha == 0.25
    assert model.get_params()["alpha"] == 0.25


# ------------------------------------------------------------------- determinism

def test_two_fits_on_identical_data_give_bit_identical_probabilities():
    """Inherited from `NNClassifier`, but the residual adds a second fitted branch
    inside the same `fit`, so the contract is re-asserted here rather than assumed.
    Gate 1's stability number is only interpretable for an estimator that has it."""
    X, y = make_dataset()
    assert_deterministic("residual_matcher", lambda: residual(0.5), X, y)


def test_fitting_leaves_no_trace_on_the_process_global_generators():
    """The base branch is fitted inside the same deterministic context as the MLP.
    `train_models.py` trains a two-tower model from process-global torch RNG in the
    same interpreter, so an estimator that reseeded anything on its way through
    would change a competitor's numbers by being run before it."""
    import random as stdlib_random

    import torch

    X, y = make_dataset()
    before = (np.random.get_state()[1].tobytes(), stdlib_random.getstate(),
              torch.random.get_rng_state().clone())
    residual(0.5).fit(X, y)
    after = (np.random.get_state()[1].tobytes(), stdlib_random.getstate(),
             torch.random.get_rng_state().clone())

    assert before[0] == after[0], "numpy global RNG was reseeded by fit()"
    assert before[1] == after[1], "stdlib random was reseeded by fit()"
    assert torch.equal(before[2], after[2]), "torch global RNG was reseeded by fit()"


# ------------------------------------------------------- selection and the verdict

def test_selection_inherits_the_folds_C_and_records_one_alpha_per_outer_fold():
    """Both selection rules at once, through the driver every model goes through.

    `C` is inherited from that outer fold's tuned-logistic selection rather than
    re-selected at a third nesting level (ADR 0003) — asserted against
    `select_by_inner_cv` directly, so it is the same value `logistic_tuned` would
    use on that partition and the comparison is exactly paired. `alpha` comes from
    the fixed grid, and `cross_fitted_oof` records the choice per fold, which is
    what the pre-registered >=3-of-5 rule is read from.
    """
    X, y = make_dataset(n_rows=75, n_features=8, n_classes=3, seed=3)

    _, _, _, chosen = cross_fitted_oof(
        X, y, n_classes=3,
        fit_predict=lambda cfg, tr, pr: (
            fit_residual(cfg, X[tr], y[tr], random_state=42, **FAST).predict_proba(X[pr])
        ),
        select_config=lambda tr: select_residual_config(X, y, tr, random_state=42, **FAST),
    )

    assert len(chosen) == N_FOLDS
    for (tr, _), (alpha, c) in zip(outer_folds(X, y), chosen):
        assert alpha in RESIDUAL_ALPHA_GRID
        assert c == select_by_inner_cv(X, y, tr, LOGISTIC_C_GRID, fit_logistic)


def test_the_base_is_refit_on_the_inner_training_subset_during_selection(monkeypatch):
    """The partition rule at the level it is actually most likely to be broken.

    `test_the_frozen_base_is_refit_on_whichever_partition_the_mlp_trains_on` asserts
    it for one direct `fit`. This one follows the real path —
    `select_residual_config` -> `select_by_inner_cv` -> `fit_residual` -> `fit` — and
    requires that every base fitted while alpha is being selected saw an
    inner-training subset, never the whole outer-training partition. Hoisting the
    base fit up one level is the natural-looking optimisation (once per fold instead
    of once per inner split) and it is exactly the Leakage the plan warns is the
    easiest thing here to get subtly wrong.
    """
    X, y = make_dataset(n_rows=75, n_features=8, n_classes=3, seed=3)
    tr, _ = next(iter(outer_folds(X, y)))
    fitted_on = []

    class Recording(ResidualMatcher):
        def _fit(self, X_fit, y_fit, soft_targets):
            fitted_on.append(len(X_fit))
            return super()._fit(X_fit, y_fit, soft_targets)

    monkeypatch.setattr(train_models, "ResidualMatcher", Recording)
    select_residual_config(X, y, tr, random_state=42, **FAST)

    inner = StratifiedKFold(INNER_SPLITS, shuffle=True, random_state=SEED)
    expected = {len(itr) for itr, _ in inner.split(X[tr], y[tr])}
    assert fitted_on, "no base was fitted at all — the spy never fired"
    assert set(fitted_on) == expected
    assert len(tr) not in expected, (
        "an inner-training subset is the same size as the outer-training partition "
        "here, so the assertion above cannot tell them apart — the test is vacuous"
    )


def test_the_selected_config_is_blind_to_the_rows_it_will_score():
    """Selection is a pure function of the outer fold's training partition, so
    corrupting that fold's held-out rows beyond recognition must return the same
    configuration. Only one fold is corrupted per run: fold k's test rows are also
    every other fold's *training* rows, so corrupting all of them at once would be
    corrupting everything."""
    X, y = make_dataset(n_rows=75, n_features=8, n_classes=3, seed=3)
    tr, te = next(iter(outer_folds(X, y)))

    clean = select_residual_config(X, y, tr, **FAST)
    corrupted = X.copy()
    corrupted[te] = np.random.default_rng(99).normal(size=(len(te), X.shape[1])) * 50.0

    assert select_residual_config(corrupted, y, tr, **FAST) == clean


def test_alpha_zero_verdict_implements_the_pre_registered_rule():
    """`alpha = 0` in >=3 of 5 outer folds is "no non-linear signal found" and
    disqualifies the Residual Matcher from being the shipped neural model. Encoded
    once, here, so the sweep reads the rule rather than restating it — a
    pre-registered threshold that gets paraphrased at the point of use is a
    threshold that can move after seeing the data."""
    disqualified = alpha_zero_verdict([(0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (0.25, 1.0), (0.5, 1.0)])
    assert disqualified["per_fold_alpha"] == [0.0, 0.0, 0.0, 0.25, 0.5]
    assert disqualified["n_folds_at_zero"] == 3
    assert disqualified["no_non_linear_signal"] is True

    survives = alpha_zero_verdict([(0.0, 1.0), (0.0, 1.0), (0.25, 1.0), (0.25, 1.0), (1.0, 1.0)])
    assert survives["n_folds_at_zero"] == 2
    assert survives["no_non_linear_signal"] is False


def test_alpha_zero_verdict_refuses_a_run_that_is_not_five_outer_folds():
    """"3 of 5" is a count, not a proportion, and it was pre-registered against this
    protocol's five outer folds. Handed three folds it would read as a majority on a
    threshold nobody registered, so it refuses instead of guessing."""
    with pytest.raises(ValueError, match="outer fold"):
        alpha_zero_verdict([(0.0, 1.0), (0.0, 1.0), (0.25, 1.0)])
