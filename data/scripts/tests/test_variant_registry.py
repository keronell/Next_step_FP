"""The 14 Variants are fully specified up front, and the control is the Incumbent NN.

"Variant" is `CONTEXT.md`'s term: one fully-specified Learned Matcher configuration
entered into the sweep, distinct from a hyperparameter setting explored inside a
fold. The plan's Step 2.2 fixes all 14 before any data is seen, which is what lets
Step 2.4 delete the pruning pass — with no separate selection stage there is no
stage that can leak.

Two things here are load-bearing rather than bookkeeping:

- **The control must be byte-for-byte the configuration `small_nn`'s recorded
  numbers came from.** The sweep varies ARGUMENTS to `nn_model.NNClassifier`; this
  ticket also had to add two constructor arguments to express Gaussian input noise
  and the SGD+cosine protocol, and a default that silently perturbed V0 would move
  the Gate-1 and Gate-2 numbers this sweep is measured against.
- **No two Variants may be the same configuration under two names**, or the 14-way
  inner-CV contest is really a 13-way one and the report's variant table lies.

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

from nn_model import NNClassifier  # noqa: E402
from sweep_variants import CONTROL, VARIANTS, build_variant  # noqa: E402


def make_dataset(n=140, d=12, n_classes=4, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)).astype(np.float32)
    y = np.tile(np.arange(n_classes), n // n_classes)
    X[np.arange(n), y % d] += 2.5  # a signal, so fits are not pure noise
    return X, y


def test_there_are_exactly_fourteen_variants_across_the_three_axes():
    assert len(VARIANTS) == 14
    axes = {}
    for v in VARIANTS.values():
        axes.setdefault(v.axis, []).append(v.name)
    # Plan Step 2.2: capacity 4 (A4 is the control), regularization 5, protocol 5.
    assert len(axes["capacity"]) == 4
    assert len(axes["regularization"]) == 5
    assert len(axes["protocol"]) == 5
    # Each Variant is filed under its own key. (`len(VARIANTS) == len(set(VARIANTS))`
    # would look like a uniqueness check and be true of any dict; the real one is
    # test_no_two_variants_are_the_same_configuration_under_two_names.)
    assert all(name == variant.name for name, variant in VARIANTS.items())
    assert CONTROL in VARIANTS


def test_no_two_variants_are_the_same_configuration_under_two_names():
    seen = {}
    for v in VARIANTS.values():
        key = (v.kind, tuple(sorted(v.kwargs.items())))
        assert key not in seen, (
            f"{v.name} and {seen[key]} are the same configuration, so the sweep is "
            "not really a 14-way contest"
        )
        seen[key] = v.name


def test_the_control_variant_predicts_identically_to_the_incumbent_network():
    """V0 is `NNClassifier`'s own defaults, and this ticket's new constructor
    arguments must be inert at their defaults.

    Bit-identity, not closeness: `small_nn`'s Gate-1 qualification (ECE 0.062,
    stability 0.615) and its Gate-2 row were measured on this exact estimator, and
    the sweep reports the control against them.
    """
    X, y = make_dataset()

    incumbent = NNClassifier(random_state=42).fit(X, y).predict_proba(X)
    control = build_variant(VARIANTS[CONTROL], random_state=42).fit(X, y).predict_proba(X)

    assert np.array_equal(control, incumbent)


def test_every_variant_builds_and_predicts_a_full_probability_simplex():
    X, y = make_dataset()
    for name, variant in VARIANTS.items():
        config = (0.5, 1.0) if variant.kind == "residual" else None
        model = build_variant(variant, random_state=42, config=config).fit(X, y)
        probs = model.predict_proba(X)
        assert probs.shape == (len(X), len(np.unique(y))), name
        assert np.allclose(probs.sum(axis=1), 1.0), name


def test_the_ensemble_is_its_own_variant_and_is_never_fused_into_the_residual():
    """Fusing them would confound "does a non-linear residual help" with "does
    seed-averaging help", and a fused winner could not be attributed to either
    (plan Step 2.2)."""
    kinds = {v.name: v.kind for v in VARIANTS.values()}
    ensembles = [n for n, k in kinds.items() if k == "ensemble"]
    residuals = [n for n, k in kinds.items() if k == "residual"]

    assert len(ensembles) == 1 and len(residuals) == 1
    assert set(ensembles).isdisjoint(residuals)
