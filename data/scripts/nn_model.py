"""Neural Learned Matcher variants — one definition, shared by both gates.

`evaluate_matchers.py` (Gate 1) and `train_models.py` (Gate 2) both import
`NNClassifier` from here. Before this module existed only Gate 2 had a network,
defined inline, so "the NN" meant whatever that one function happened to do — and
Gate 1 could not score the same object Gate 2 selected.

`ResidualMatcher` is the second definition here: the plan's Step 2.3 variant, a
frozen logistic branch plus a gated MLP correction. It subclasses `NNClassifier`
through one seam (`_logits`) so the training loop, class weighting, early-stopping
split and determinism contract are shared rather than copied.

`SeedEnsemble` is the third: the sweep's protocol Variant C3, `n_members` networks
differing only in seed and averaged in probability. It stays a Variant in its own
right and is never fused into `ResidualMatcher` — fusing would confound "does a
non-linear residual help" with "does seed-averaging help" (plan Step 2.2).

The Round-1 sweep (DEV-93) varies **arguments** to these classes rather than
editing them; `input_noise`, `optimizer`, `lr_schedule` and `momentum` were added
for exactly that reason, and their defaults are inert so V0 is unchanged. The
learning curve (DEV-96) added `val_size` on the same terms — it needs an ABSOLUTE
early-stopping split size, `val_fraction` is a float, and `None` leaves the
`val_fraction` call untouched rather than re-deriving the same number.

Nothing here is Selected, Servable or Deployable, and clearing Gate 1 makes a
configuration Qualified and nothing more (see `CONTEXT.md`).

## Determinism is part of the contract, not a nicety

Gate 1 scores recommendation stability as top-2 set agreement between sub-models
trained on inner resamples of a fold's training partition. For logistic that
variation comes *only* from the training subset, because the estimator is
near-deterministic. A network that also varied from its own dropout draws and
weight init would be scored on a strictly noisier estimator than its competitors,
and Gate 1's stability threshold could then fire on a measurement artifact rather
than on real instability — admitting or rejecting a configuration for the wrong
reason, and taking the plan's Step-2.7 ship floor with it.

So `random_state` is an explicit constructor argument and every `fit()` re-seeds
torch and numpy from it and runs under deterministic backend kernels. Two fits on
identical data produce bit-identical `predict_proba` output, leaving the training
subset as the only surviving source of variation — the same thing being measured
for logistic. `data/scripts/tests/test_nn_model.py` holds that contract; a torch
upgrade that reintroduces nondeterminism fails there, and again at the runtime
assertion Gate 1 runs before it trusts any stability number.

Determinism is guaranteed *within a machine and interpreter*: torch's CPU kernels
are deterministic for a fixed thread count, which does not vary between two fits in
one process. Across machines it is the same guarantee the lockfile gives — see
`data/scripts/README.md`.

## Hard and soft targets

Gate 1 feeds `(X, y)` hard labels, exactly like every other gate candidate, so the
candidates are comparable. Gate 2 additionally passes `soft_targets` — the panel's
vote distribution — which is a genuinely different training objective and stays a
Gate-2 challenger. The asymmetry is deliberate and is handled by the pattern
already in the repo: export revalidates the *exact shipped configuration* against
the Gate-1 thresholds, because qualification never transfers across configurations.
"""
from __future__ import annotations

import random
from contextlib import contextmanager

import numpy as np
import torch
import torch.nn as nn
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.extmath import softmax as _sklearn_softmax

# V0 in the plan's variant sweep (Step 2.2): the configuration the recorded
# small_nn numbers were produced with. Kept as defaults so the sweep varies
# arguments rather than editing this module.
DEFAULT_HIDDEN_SIZES = (64, 32)
DEFAULT_DROPOUT = 0.3
DEFAULT_LR = 1e-3
DEFAULT_WEIGHT_DECAY = 1e-4
DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_EPOCHS = 400
DEFAULT_PATIENCE = 30
DEFAULT_VAL_FRACTION = 0.15
# Added for the Round-1 sweep (DEV-93), which needs Gaussian input noise and an
# SGD+momentum/cosine protocol as Variants. Their defaults are the inert ones: at
# `input_noise = 0.0` no generator is drawn from at all, and "adam"/None is the
# optimizer V0 was always trained with, so the control Variant stays bit-identical
# to the estimator `small_nn`'s recorded numbers came from.
DEFAULT_INPUT_NOISE = 0.0
DEFAULT_OPTIMIZER = "adam"
DEFAULT_LR_SCHEDULE = None
DEFAULT_MOMENTUM = 0.9
# Added for the learning curve (DEV-96), which applies one validation rule at every
# curve point: `n_val = max(n_classes, ceil(0.15 * n_train))`. That is an absolute
# size, and `val_fraction` is a float handed to `train_test_split` -- which takes
# `ceil(fraction * n)`, so `n_val / n_train` is not guaranteed to come back on the
# integer it was built from. `None` is the inert default: the `val_fraction` path is
# then the identical call it has always been, which is what keeps the control Variant
# bit-identical and `small_nn`'s recorded Gate-1 numbers describing this estimator.
DEFAULT_VAL_SIZE = None


@contextmanager
def _deterministic_fit(seed: int):
    """Seed every generator a fit draws from, disable nondeterministic backend
    kernels, and leave no trace of either on the way out.

    Seeding all three generators is deliberate. Torch seeds weight init, dropout
    masks and the batch permutation. Numpy and the stdlib `random` cover
    scikit-learn's stratified validation split — which decides *which rows* the
    early-stopping criterion sees, and therefore which epoch is selected. The split
    is already passed an explicit `random_state`, so seeding them is belt-and-braces
    against a future code path inside `fit` that reaches for a global generator.

    All of it is process-global state, so all of it is restored. An estimator that
    reseeded `np.random` as a side effect of being fitted would be an unpleasant
    surprise for anything sharing the interpreter — `evaluate_matchers.py` fits
    logistic and lightgbm in the same run, and `train_models.py` also trains a
    two-tower model under torch. The gate's numbers must not depend on which
    candidate happened to be fitted first."""
    prev_random = random.getstate()
    prev_numpy = np.random.get_state()
    prev_torch = torch.random.get_rng_state()
    prev_algorithms = torch.are_deterministic_algorithms_enabled()
    prev_cudnn_deterministic = torch.backends.cudnn.deterministic
    prev_cudnn_benchmark = torch.backends.cudnn.benchmark

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():  # pragma: no cover - CPU-only training stack
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    try:
        yield
    finally:
        torch.backends.cudnn.benchmark = prev_cudnn_benchmark
        torch.backends.cudnn.deterministic = prev_cudnn_deterministic
        torch.use_deterministic_algorithms(prev_algorithms)
        torch.random.set_rng_state(prev_torch)
        np.random.set_state(prev_numpy)
        random.setstate(prev_random)


def class_weights(y: np.ndarray, n_classes: int) -> np.ndarray:
    """Inverse-frequency weights, matching sklearn's `class_weight="balanced"` so
    the network is class-balanced on the same terms as logistic and lightgbm."""
    counts = np.bincount(y, minlength=n_classes).astype(float)
    return counts.sum() / np.maximum(counts, 1) / n_classes


class _MLP(nn.Module):
    """Feed-forward trunk: d_in -> *hidden_sizes -> n_classes, ReLU + dropout.

    At the shipped feature layout (features-v4: 2*18 questions + 3*16 careers = 84)
    with the default hidden sizes this is 84 -> 64 -> 32 -> 16."""

    def __init__(self, d_in: int, n_classes: int, hidden_sizes, dropout: float):
        super().__init__()
        layers: list[nn.Module] = []
        prev = d_in
        for width in hidden_sizes:
            layers += [nn.Linear(prev, width), nn.ReLU(), nn.Dropout(dropout)]
            prev = width
        layers.append(nn.Linear(prev, n_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


class NNClassifier(BaseEstimator, ClassifierMixin):
    """Deterministic MLP classifier with the estimator interface both gates expect.

    Standardization is internal and fitted on the training rows only, so the
    estimator can be handed raw feature matrices by `cv_oof_and_stability()`
    exactly like the logistic pipeline is — no scaling leaks across a fold
    boundary.

    Parameters mirror the plan's V0 configuration. `random_state` has no default:
    a caller that forgets it would silently reintroduce the nondeterminism this
    module exists to remove.
    """

    def __init__(
        self,
        random_state: int,
        hidden_sizes=DEFAULT_HIDDEN_SIZES,
        dropout: float = DEFAULT_DROPOUT,
        lr: float = DEFAULT_LR,
        weight_decay: float = DEFAULT_WEIGHT_DECAY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_epochs: int = DEFAULT_MAX_EPOCHS,
        patience: int = DEFAULT_PATIENCE,
        val_fraction: float = DEFAULT_VAL_FRACTION,
        input_noise: float = DEFAULT_INPUT_NOISE,
        optimizer: str = DEFAULT_OPTIMIZER,
        lr_schedule: str | None = DEFAULT_LR_SCHEDULE,
        momentum: float = DEFAULT_MOMENTUM,
        val_size: int | None = DEFAULT_VAL_SIZE,
    ):
        self.random_state = random_state
        self.hidden_sizes = hidden_sizes
        self.dropout = dropout
        self.lr = lr
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.val_fraction = val_fraction
        self.input_noise = input_noise
        self.optimizer = optimizer
        self.lr_schedule = lr_schedule
        self.momentum = momentum
        self.val_size = val_size

    # ------------------------------------------------------------------ fit
    def fit(self, X, y, soft_targets: np.ndarray | None = None) -> "NNClassifier":
        """Fit on hard labels `y`, or on `soft_targets` when supplied.

        `soft_targets` is a (n_rows, n_classes) distribution whose columns follow
        `classes_` order. `y` is still required even when it is supplied: it
        provides the class weights and the stratification for the early-stopping
        split, so the two paths differ only in the target of the loss."""
        with _deterministic_fit(self.random_state):
            return self._fit(X, y, soft_targets)

    def _fit(self, X, y, soft_targets):
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)
        y_idx = np.searchsorted(self.classes_, y)

        if soft_targets is None:
            targets = np.eye(n_classes, dtype=np.float32)[y_idx]
        else:
            targets = np.asarray(soft_targets, dtype=np.float32)
            if targets.shape != (len(X), n_classes):
                raise ValueError(
                    f"soft_targets has shape {targets.shape}, expected "
                    f"{(len(X), n_classes)} — columns must follow classes_ order"
                )

        # Standardize on training statistics only; kept for predict_proba.
        self.mean_ = X.mean(axis=0)
        self.scale_ = X.std(axis=0) + 1e-8
        Xs = (X - self.mean_) / self.scale_

        # An int `test_size` is taken literally by train_test_split; a float is
        # `ceil(fraction * n)`. Passing `val_fraction` unless an absolute size was
        # asked for keeps the default path the identical call it has always been --
        # `val_size=None` must not so much as re-derive the number.
        train_idx, val_idx = train_test_split(
            np.arange(len(Xs)),
            test_size=self.val_fraction if self.val_size is None else self.val_size,
            stratify=y_idx,
            random_state=self.random_state,
        )
        # What the split ACTUALLY held out, not what was requested. The learning
        # curve reports this per point: "the rounding landed where the rule says" is
        # a claim about a number, and the number has to be readable to make it.
        self.n_val_ = int(len(val_idx))
        sample_w = torch.tensor(class_weights(y_idx, n_classes)[y_idx], dtype=torch.float32)

        model = _MLP(X.shape[1], n_classes, tuple(self.hidden_sizes), self.dropout)
        opt = self._build_optimizer(model)
        scheduler = (
            torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=self.max_epochs)
            if self.lr_schedule == "cosine" else None
        )
        Xt = torch.tensor(Xs)
        Tt = torch.tensor(targets)
        train_t = torch.tensor(train_idx)
        val_t = torch.tensor(val_idx)

        def loss_on(idx, training: bool):
            model.train(training)
            logp = torch.log_softmax(self._logits(model, Xt, idx), dim=1)
            # Soft-target cross-entropy, class-weighted per sample. With one-hot
            # targets this reduces exactly to weighted hard-label cross-entropy.
            return (-(Tt[idx] * logp).sum(dim=1) * sample_w[idx]).mean()

        best_state, best_val, waited = None, np.inf, 0
        for _ in range(self.max_epochs):
            for batch in torch.randperm(len(train_idx)).split(self.batch_size):
                opt.zero_grad()
                loss_on(train_t[batch], training=True).backward()
                opt.step()
            if scheduler is not None:
                scheduler.step()
            with torch.no_grad():
                val = float(loss_on(val_t, training=False))
            if val < best_val - 1e-4:
                best_val = val
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                waited = 0
            else:
                waited += 1
                if waited >= self.patience:
                    break

        if best_state is not None:
            model.load_state_dict(best_state)
        model.eval()
        self.model_ = model
        self.n_features_in_ = X.shape[1]
        return self

    def _build_optimizer(self, model):
        """Adam by default; SGD+momentum for the sweep's protocol Variant.

        Weight decay goes to the optimizer in both cases, so the regularization
        axis means the same thing whichever protocol is selected."""
        if self.optimizer == "adam":
            return torch.optim.Adam(
                model.parameters(), lr=self.lr, weight_decay=self.weight_decay
            )
        if self.optimizer == "sgd":
            return torch.optim.SGD(
                model.parameters(), lr=self.lr, momentum=self.momentum,
                weight_decay=self.weight_decay,
            )
        raise ValueError(f"unknown optimizer {self.optimizer!r}, expected 'adam' or 'sgd'")

    def _noisy(self, model, x):
        """Gaussian input noise, training only — the sweep's regularization Variant.

        Returns `x` untouched at the default `input_noise = 0.0`, and draws from no
        generator in that case. That is what keeps V0 bit-identical: an
        unconditional `randn_like` scaled by zero would still advance torch's RNG
        and shift every subsequent dropout mask and batch permutation.

        `model.training` rather than a flag of our own, because the caller has
        already set it and two sources of truth for "is this a training pass" is
        exactly how noise ends up leaking into inference."""
        if self.input_noise <= 0.0 or not model.training:
            return x
        return x + torch.randn_like(x) * self.input_noise

    def _logits(self, model, Xt, idx):
        """The logit vector the loss is measured on, for the rows `idx`.

        A seam, not indirection for its own sake: `ResidualMatcher` overrides this
        one expression to add its frozen linear branch, and everything else about
        the training loop — the class weights, the stratified early-stopping split,
        which epoch gets selected — is then shared with this class rather than
        copied into a second one that could drift. For `NNClassifier` the logits are
        the MLP's own output, so nothing about `small_nn` changes."""
        return model(self._noisy(model, Xt[idx]))

    # -------------------------------------------------------------- predict
    def _mlp_output(self, X):
        """The trunk's raw logits for `X`, standardized with the training
        statistics and with dropout off.

        Shared with `ResidualMatcher`, which needs the same tensor as a correction
        term rather than as the whole logit vector. Two copies of this would be two
        copies of the standardization contract — the scaler is fitted on training
        rows only and kept on the estimator precisely so inference reproduces it,
        and a second copy that drifted would be silent."""
        Xs = (np.asarray(X, dtype=np.float32) - self.mean_) / self.scale_
        self.model_.eval()  # no dropout at inference — predictions are a function of X alone
        with torch.no_grad():
            return self.model_(torch.tensor(Xs))

    def predict_proba(self, X) -> np.ndarray:
        return torch.softmax(self._mlp_output(X), dim=1).numpy().astype(np.float64)

    def predict(self, X) -> np.ndarray:
        return self.classes_[self.predict_proba(X).argmax(axis=1)]


class SeedEnsemble(BaseEstimator, ClassifierMixin):
    """`n_members` `NNClassifier`s differing only in seed, averaged in PROBABILITY.

    The sweep's protocol Variant C3. Averaging probabilities rather than logits is
    the choice that keeps the result a distribution without a renormalisation step,
    and it is the form the plan costed: integrated gradients is linear in the model
    function, so attribution over a probability-averaged ensemble is just the
    average of the members' attributions — ensembling costs artifact size and
    serve-time compute, not explainability.

    **It stays a separate Variant and is never fused into the Residual Matcher.**
    Fusing would confound "does a non-linear residual help" with "does
    seed-averaging help", and a fused winner could not be attributed to either
    (plan Step 2.2). Round 2 may test ensembling on top of a Round-1 winner; that is
    a different question asked after this one is answered.

    Deterministic on the same terms as its members: seeds are `random_state + i`,
    fixed by construction, and each member restores the global generators it
    touched. So `assert_deterministic` holds for the ensemble exactly when it holds
    for one member, and Gate 1's stability number stays interpretable.

    **Not `sklearn.clone`-safe**, and deliberately not made so. `member_kwargs` is
    collected with `**`, which `BaseEstimator.get_params` cannot see, so a `clone()`
    would silently return an ensemble of DEFAULT members — a wrong model that still
    runs. Nothing in this pipeline clones: `cv_oof_and_stability`,
    `assert_deterministic` and the sweep all construct through factories that call
    the constructor directly. Spelling the parameters out to satisfy `get_params`
    would mean restating every `NNClassifier` argument here and keeping the two lists
    in sync forever, which is a larger and more silent failure mode than the one it
    removes. If a caller ever needs `clone`, give this class explicit parameters
    then — and know that is what changed.
    """

    def __init__(self, random_state: int, n_members: int = 5, **member_kwargs):
        self.random_state = random_state
        self.n_members = n_members
        self.member_kwargs = member_kwargs

    def fit(self, X, y, soft_targets: np.ndarray | None = None) -> "SeedEnsemble":
        self.members_ = [
            NNClassifier(random_state=self.random_state + i, **self.member_kwargs)
            .fit(X, y, soft_targets=soft_targets)
            for i in range(self.n_members)
        ]
        self.classes_ = self.members_[0].classes_
        self.n_features_in_ = self.members_[0].n_features_in_
        return self

    def predict_proba(self, X) -> np.ndarray:
        return np.mean([m.predict_proba(X) for m in self.members_], axis=0)

    def predict(self, X) -> np.ndarray:
        return self.classes_[self.predict_proba(X).argmax(axis=1)]


def frozen_logistic(C: float, random_state: int):
    """The Residual Matcher's linear branch — and `train_models.fit_logistic`'s
    estimator, from this one construction site.

    ADR 0006's argument for the Residual Matcher rests on its base being *exactly*
    the Incumbent's configuration on the same partition, which is what turns "does
    the residual add anything?" into an exactly paired comparison. A second
    definition that drifted by one keyword would leave that claim quietly false
    while every test still passed, so there is only one.

    `random_state` is threaded through for completeness. The lbfgs solver does not
    consume it, so the fitted base is a function of `C` and the training partition
    alone — which is why the experiment seed the sweep varies reaches only the MLP
    branch. `test_residual_matcher.py` holds that.
    """
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=C, max_iter=5000, class_weight="balanced", random_state=random_state),
    )


class ResidualMatcher(NNClassifier):
    """`logits = frozen_logistic_logits + alpha * MLP(x)`, summed BEFORE the softmax.

    Both branches see the same input and emit a full per-career logit vector. The
    linear branch is fitted on whatever partition the MLP trains on and then held
    fixed; `alpha` is a **hyperparameter** selected by inner CV from the grid in
    `train_models.RESIDUAL_ALPHA_GRID`. Full rationale in ADR 0006; the vocabulary
    ("Residual Matcher", not "C4" or "hybrid") is `CONTEXT.md`'s.

    ## Three things that are load-bearing, not incidental

    **The linear branch is frozen, and that is the point.** An earlier revision
    trained both branches jointly, warm-started at the logistic solution, and
    claimed this made the model structurally never worse than logistic. That claim
    was false: initialisation constrains only the starting predictions, training
    minimises soft-target cross-entropy while the reported metric is top-2, and
    early stopping selects on validation loss — so the net can and does finish below
    its own initialisation. Do not "fix" this by unfreezing. At n=232 with 84
    features and 16 classes the binding constraint is variance, not expressiveness,
    and a trainable linear branch would spend scarce capacity re-learning structure
    already available in closed form.

    **`alpha` is not learned.** A learnable alpha initialised at zero is pushed off
    zero immediately, because moving it reduces training loss — which reproduces the
    retracted claim above with extra steps. It is selected from a fixed grid on
    inner-CV top-2, the same basis every other nested selection in this pipeline
    uses.

    **The base is refit inside `fit`, never handed in.** That is what makes "the
    frozen base is refit on whichever partition the MLP trains on" structural: there
    is no call site that *could* hoist it to the outer-training partition, which is
    the plan's named easiest-thing-to-get-subtly-wrong and would be Leakage in the
    sense `CONTEXT.md` reserves the word for.

    ## Why `alpha = 0` is exactly logistic regression, and not approximately

    For a multiclass problem sklearn's `LogisticRegression.predict_proba` *is*
    `softmax(decision_function(X))`. So the base branch contributes decision values
    rather than `log(predict_proba)`, and the same `sklearn.utils.extmath.softmax`
    is applied to the sum — the identical function sklearn calls, imported rather
    than reimplemented, so the identity cannot decay into "close" if sklearn's
    operation order ever changes. At `alpha = 0` the correction term is exactly
    `0.0`, adding it changes no bit of the base logits, and `predict_proba` returns
    sklearn's own array. `predict_proba` has **no branch on alpha**: a short-circuit
    would make the acceptance test assert something about itself.

    The MLP is still trained at `alpha = 0` rather than skipped. The loss's
    gradient with respect to every MLP parameter is identically zero there — held
    by `test_at_alpha_zero_the_loss_carries_no_gradient_into_the_mlp` — and the
    validation loss is therefore constant, so early stopping ends the fit after one
    patience window. That is the whole cost of not having a branch on `alpha` in the
    forward pass.
    """

    def __init__(
        self,
        random_state: int,
        alpha: float,
        logistic_C: float,
        hidden_sizes=DEFAULT_HIDDEN_SIZES,
        dropout: float = DEFAULT_DROPOUT,
        lr: float = DEFAULT_LR,
        weight_decay: float = DEFAULT_WEIGHT_DECAY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_epochs: int = DEFAULT_MAX_EPOCHS,
        patience: int = DEFAULT_PATIENCE,
        val_fraction: float = DEFAULT_VAL_FRACTION,
        input_noise: float = DEFAULT_INPUT_NOISE,
        optimizer: str = DEFAULT_OPTIMIZER,
        lr_schedule: str | None = DEFAULT_LR_SCHEDULE,
        momentum: float = DEFAULT_MOMENTUM,
        val_size: int | None = DEFAULT_VAL_SIZE,
    ):
        super().__init__(
            random_state=random_state,
            hidden_sizes=hidden_sizes,
            dropout=dropout,
            lr=lr,
            weight_decay=weight_decay,
            batch_size=batch_size,
            max_epochs=max_epochs,
            patience=patience,
            val_fraction=val_fraction,
            input_noise=input_noise,
            optimizer=optimizer,
            lr_schedule=lr_schedule,
            momentum=momentum,
            val_size=val_size,
        )
        self.alpha = alpha
        self.logistic_C = logistic_C

    # ------------------------------------------------------------------ fit
    def _fit(self, X, y, soft_targets):
        Xb = np.asarray(X)
        if len(np.unique(y)) < 3:
            raise ValueError(
                "ResidualMatcher needs more than two classes: sklearn's "
                "LogisticRegression.predict_proba takes a sigmoid path rather than "
                "a multiclass softmax one at two classes, so the additive-logit "
                "form would not collapse to it at alpha=0 and would be scoring "
                "something other than what it claims."
            )

        # Fitted here rather than accepted as an argument — see the class docstring.
        # Inside `fit`'s deterministic context, so the base cannot leave a trace on
        # the process-global generators either.
        self.base_ = frozen_logistic(self.logistic_C, self.random_state).fit(Xb, y)
        # float32 to match the MLP branch it is summed with during training.
        # `predict_proba` deliberately re-reads the base in float64 instead: that is
        # where the bit-identity with sklearn has to hold, and sklearn works in
        # float64.
        self._base_logits_t = torch.tensor(
            self.base_.decision_function(Xb), dtype=torch.float32
        )
        try:
            return super()._fit(Xb, y, soft_targets)
        finally:
            # Only the training loop indexes it, and it is sized to the training
            # rows; keeping it on the fitted object would be a stale array shaped
            # like a live one.
            del self._base_logits_t

    def _logits(self, model, Xt, idx):
        """The model equation, and the one place the two branches meet: summed here,
        *before* the `log_softmax` the caller applies. The base tensor carries no
        `requires_grad`, so the frozen branch contributes to the loss without
        appearing in it."""
        return self._base_logits_t[idx] + self.alpha * model(self._noisy(model, Xt[idx]))

    # -------------------------------------------------------------- predict
    def predict_proba(self, X) -> np.ndarray:
        Xb = np.asarray(X)
        base = self.base_.decision_function(Xb)
        correction = self._mlp_output(Xb).numpy().astype(np.float64)
        return _sklearn_softmax(base + self.alpha * correction, copy=False)
