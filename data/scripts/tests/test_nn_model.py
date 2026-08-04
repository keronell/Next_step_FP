"""The determinism contract of `nn_model.NNClassifier` (plan Step 2.1).

Why the contract exists is argued once, at
`evaluate_matchers.assert_deterministic` — in short, Gate 1's stability number is
only interpretable for an estimator whose refits on identical data agree. What
these tests add is that it is the kind of property a torch upgrade can silently
take away, months after anyone last thought about it, and the resulting number
would look perfectly reasonable. So it fails loudly here as well as at runtime.

Run from repo root with the TRAINING venv (this module needs torch; `Scripts/`
replaces `bin/` on Windows, as everywhere in data/scripts/README.md):

    data/venv-training/bin/python -m pytest data/scripts/tests -q

Under the service-test venv this module skips whole; `test_env_manifest.py` still
runs there, which is what proves the manifest stayed stdlib-only.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

np = pytest.importorskip("numpy")
pytest.importorskip("torch")

pytest.importorskip("sklearn")
pytest.importorskip("lightgbm")

from evaluate_matchers import assert_deterministic  # noqa: E402
from nn_model import NNClassifier, SeedEnsemble  # noqa: E402


def make_dataset(n_rows: int = 90, n_features: int = 12, n_classes: int = 6, seed: int = 0):
    """A small, class-balanced, learnable table — deliberately not the real feature
    parquet: these tests are about the estimator's contract, not about the dataset."""
    rng = np.random.default_rng(seed)
    y = np.repeat(np.arange(n_classes), n_rows // n_classes)
    centers = rng.normal(size=(n_classes, n_features)) * 2.0
    X = centers[y] + rng.normal(size=(len(y), n_features))
    return X.astype(np.float64), y


def test_two_fits_on_identical_data_give_bit_identical_probabilities():
    """The contract Gate-1 stability rests on: with `random_state` fixed, the only
    surviving source of variation between two fits is the training subset — the
    same thing being measured for logistic."""
    X, y = make_dataset()
    a = NNClassifier(random_state=42, max_epochs=25).fit(X, y).predict_proba(X)
    b = NNClassifier(random_state=42, max_epochs=25).fit(X, y).predict_proba(X)
    # Bit-identical, not np.allclose: "close enough" is exactly the tolerance that
    # would let real nondeterminism through as a small stability wobble.
    assert np.array_equal(a, b)


def test_the_seed_is_what_makes_the_fits_identical():
    """Guards the test above from passing for the wrong reason. A model that
    collapsed to a constant, or one that ignored `random_state` because the
    seeding was wired to a module global, would satisfy bit-identity trivially."""
    X, y = make_dataset()
    a = NNClassifier(random_state=42, max_epochs=25).fit(X, y).predict_proba(X)
    c = NNClassifier(random_state=7, max_epochs=25).fit(X, y).predict_proba(X)
    assert not np.array_equal(a, c)


def test_the_network_actually_learns_the_classes():
    """Determinism on a model that predicts nothing would be worthless. Chance is
    1/6 here; the assertion is deliberately loose because this is a smoke test of
    the training loop, not a quality measurement."""
    X, y = make_dataset()
    model = NNClassifier(random_state=42).fit(X, y)
    assert (model.predict(X) == y).mean() > 0.8


def test_fitting_leaves_no_trace_on_the_process_global_generators():
    """Seeding is process-global state. Gate 1 fits logistic and lightgbm in the
    same interpreter as the network, so an estimator that reseeded `np.random` as a
    side effect of being fitted would make its competitors' numbers depend on
    evaluation order."""
    import random as stdlib_random

    import torch

    X, y = make_dataset()
    before = (np.random.get_state()[1].tobytes(), stdlib_random.getstate(),
              torch.random.get_rng_state().clone())
    NNClassifier(random_state=42, max_epochs=10).fit(X, y)
    after = (np.random.get_state()[1].tobytes(), stdlib_random.getstate(),
             torch.random.get_rng_state().clone())

    assert before[0] == after[0], "numpy global RNG was reseeded by fit()"
    assert before[1] == after[1], "stdlib random was reseeded by fit()"
    assert torch.equal(before[2], after[2]), "torch global RNG was reseeded by fit()"


def test_deterministic_kernel_settings_are_restored_after_a_fit():
    """`use_deterministic_algorithms` is global and makes unrelated torch ops raise
    when they have no deterministic implementation — train_models.py trains a
    two-tower model in the same process."""
    import torch

    X, y = make_dataset()
    before = torch.are_deterministic_algorithms_enabled()
    NNClassifier(random_state=42, max_epochs=10).fit(X, y)
    assert torch.are_deterministic_algorithms_enabled() == before


# --------------------------------------------------------------------------
# The Gate-1 precondition: the stability floor may not fire on a measurement
# artifact, so the assertion runs for every candidate before any stability
# number is trusted (plan Step 3.2).
# --------------------------------------------------------------------------

class _NondeterministicStub:
    """Stands in for an estimator whose predictions vary between refits on
    identical data — the exact defect the assertion exists to catch."""

    def fit(self, X, y):
        self._noise = np.random.default_rng().normal(size=(len(X), 2))
        return self

    def predict_proba(self, X):
        return np.abs(self._noise) / np.abs(self._noise).sum(axis=1, keepdims=True)


def test_determinism_assertion_accepts_a_deterministic_candidate():
    X, y = make_dataset()
    assert_deterministic("small_nn", lambda: NNClassifier(random_state=42, max_epochs=15), X, y)


def test_determinism_assertion_rejects_a_candidate_that_varies_between_refits():
    """It must fail loudly and name the candidate. A silent pass here would let
    Gate 1 score the network on a noisier estimator than its competitors."""
    X, y = make_dataset()
    with pytest.raises(SystemExit) as excinfo:
        assert_deterministic("stub", _NondeterministicStub, X, y)
    assert "stub" in str(excinfo.value)


# ------------------------------------------------------------------- the ensemble


def test_the_seed_ensemble_inherits_the_determinism_contract():
    """The ensemble carries the contract too, and DEV-95 put it on the critical path.

    Every Round-2 candidate is Ship-Floor-eligible, and most of them are seed
    ensembles. The stability half of that floor is hard and unmitigable: it reads all
    sub-model disagreement as training-subset variation, which is only valid for an
    estimator whose refits on identical data agree. Members are seeded
    `random_state + i` and each restores the global generators it touched, so the
    property follows from theirs — asserted rather than deduced because the deduction
    has two steps and the failure would look like a stability wobble rather than
    like a bug."""
    X, y = make_dataset()
    assert_deterministic(
        "seed_ensemble",
        lambda: SeedEnsemble(random_state=42, n_members=3, hidden_sizes=(8,), max_epochs=10),
        X, y,
    )


def test_the_ensemble_is_not_one_member_wearing_a_hat():
    """Guards the test above from passing for the wrong reason: an ensemble that
    built its members with one seed, or returned the first member's probabilities,
    would be bit-identically deterministic and would also be pointless."""
    X, y = make_dataset()
    fast = {"hidden_sizes": (8,), "max_epochs": 10}

    ensemble = SeedEnsemble(random_state=42, n_members=3, **fast).fit(X, y).predict_proba(X)
    member = NNClassifier(random_state=42, **fast).fit(X, y).predict_proba(X)

    assert not np.array_equal(ensemble, member)
    assert np.allclose(ensemble.sum(axis=1), 1.0)
