"""A neural Learned Matcher variant — one definition, shared by both gates.

`evaluate_matchers.py` (Gate 1) and `train_models.py` (Gate 2) both import
`NNClassifier` from here. Before this module existed only Gate 2 had a network,
defined inline, so "the NN" meant whatever that one function happened to do — and
Gate 1 could not score the same object Gate 2 selected.

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
from sklearn.model_selection import train_test_split

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

        train_idx, val_idx = train_test_split(
            np.arange(len(Xs)),
            test_size=self.val_fraction,
            stratify=y_idx,
            random_state=self.random_state,
        )
        sample_w = torch.tensor(class_weights(y_idx, n_classes)[y_idx], dtype=torch.float32)

        model = _MLP(X.shape[1], n_classes, tuple(self.hidden_sizes), self.dropout)
        opt = torch.optim.Adam(model.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        Xt = torch.tensor(Xs)
        Tt = torch.tensor(targets)
        train_t = torch.tensor(train_idx)
        val_t = torch.tensor(val_idx)

        def loss_on(idx, training: bool):
            model.train(training)
            logp = torch.log_softmax(model(Xt[idx]), dim=1)
            # Soft-target cross-entropy, class-weighted per sample. With one-hot
            # targets this reduces exactly to weighted hard-label cross-entropy.
            return (-(Tt[idx] * logp).sum(dim=1) * sample_w[idx]).mean()

        best_state, best_val, waited = None, np.inf, 0
        for _ in range(self.max_epochs):
            for batch in torch.randperm(len(train_idx)).split(self.batch_size):
                opt.zero_grad()
                loss_on(train_t[batch], training=True).backward()
                opt.step()
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

    # -------------------------------------------------------------- predict
    def predict_proba(self, X) -> np.ndarray:
        Xs = (np.asarray(X, dtype=np.float32) - self.mean_) / self.scale_
        self.model_.eval()  # no dropout at inference — predictions are a function of X alone
        with torch.no_grad():
            probs = torch.softmax(self.model_(torch.tensor(Xs)), dim=1).numpy()
        return probs.astype(np.float64)

    def predict(self, X) -> np.ndarray:
        return self.classes_[self.predict_proba(X).argmax(axis=1)]
