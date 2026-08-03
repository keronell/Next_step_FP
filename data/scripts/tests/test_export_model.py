"""`export_model.py`: sklearn-versus-served parity for the LINEAR artifact.

DEV-97 asks whether the linear path already had the analogue of the neural parity
tests. It did not — `services/matching/tests/test_matching_with_model.py` says
"shape parity" in its docstring, but it means the *response* shape, and it drives
`MatcherModel` from hand-built artifacts with round coefficients. Nothing anywhere
compared the fitted sklearn estimator's probabilities against the stdlib
reimplementation that actually serves them. This module is that check.

It matters for the same reason the neural one does, and slightly more quietly: the
linear serving path reimplements the forward pass in **pure stdlib `math`** rather
than reusing sklearn, so a divergence would not announce itself as an import error
or a shape mismatch — it would just serve different percentages than the ones Gate 2
measured.

Run from repo root with the TRAINING venv (this module needs sklearn):

    data/venv-training/bin/python -m pytest data/scripts/tests -q

`MatcherModel` imports only `app.services.feature_builder`, which reaches
`common.data` and stops there — so unlike the neural path this one needs no stub for
`common.config`.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "data" / "scripts"))

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("pandas")

import pandas as pd  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

sys.path[:0] = [str(REPO_ROOT / "services"), str(REPO_ROOT / "services" / "matching")]

from app.services.matcher_model import MatcherModel  # noqa: E402
from train_models import apply_temperature  # noqa: E402

TRAINING_DIR = REPO_ROOT / "data" / "training"
ARTIFACT = REPO_ROOT / "data" / "models" / "matcher_logistic_v2.json"

#: Agreement required between sklearn and the stdlib serving path.
#:
#: Both compute in float64 here, so unlike the neural case there is no dtype gap to
#: absorb — only summation order. `MatcherModel` accumulates the dot product with a
#: Python `sum()` over 84 terms while sklearn uses a BLAS gemm, which reassociates.
#: The measured maximum over the complete dataset is ~1e-15, so this bar is many
#: orders of magnitude above the noise and still far below any difference that could
#: change a displayed percentage.
PARITY_TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.exists():
        pytest.skip(f"{ARTIFACT} not present - run export_model.py")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dataset():
    meta = json.loads((TRAINING_DIR / "dataset_metadata.json").read_text(encoding="utf-8"))
    df = pd.read_parquet(TRAINING_DIR / "train_features.parquet")
    feature_names = meta["feature_names"]
    careers = [n[: -len("_fit")] for n in feature_names if n.endswith("_fit")]
    X = df[feature_names].to_numpy(dtype=float)
    y = df["label_top1"].map({c: i for i, c in enumerate(careers)}).to_numpy()
    return feature_names, careers, X, y


@pytest.fixture(scope="module")
def refit(artifact, dataset):
    """The exact configuration the artifact records, refitted on all rows.

    Read from the artifact's own `training` block rather than retyped, so this
    cannot drift from what was exported.
    """
    _, _, X, y = dataset
    training = artifact["training"]
    pipeline = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=training["C"], max_iter=5000,
                           class_weight=training["class_weight"],
                           random_state=training["seed"]),
    )
    return pipeline.fit(X, y)


def served(model: MatcherModel, X, careers) -> np.ndarray:
    return np.array([[model.predict_proba(list(row))[c] for c in careers] for row in X])


def tempered_reference(pipeline, X, temperature: float) -> np.ndarray:
    """sklearn's own probabilities at the artifact's temperature, in LOGIT space.

    `train_models.apply_temperature` works in probability space and therefore has to
    `clip(probs, 1e-9, 1.0)` before taking a log. For a linear model the two are the
    same function wherever the clip does not bind, since `log softmax(z) = z -
    logsumexp(z)` and softmax removes the additive constant — but off-distribution
    inputs drive sklearn's probabilities to ~1e-47, where the clip binds hard and
    `apply_temperature` flattens them to a floor that `MatcherModel` never applies.

    Comparing against the clipped version there would report a 4.0e-8 "parity
    failure" that is really a difference between two reference implementations, not
    between the fitted model and the served one. So the reference is the
    unclipped logit-space quantity, which is exactly what the artifact's
    `temperature` field means to the serving path.
    """
    z = pipeline.decision_function(X) / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def test_the_shipped_linear_artifact_is_the_model_that_was_fitted(artifact, refit):
    """The serialized coefficients must be the ones sklearn produced. Without this,
    parity below could hold between the artifact and a *different* refit."""
    classifier = refit.named_steps["logisticregression"]
    scaler = refit.named_steps["standardscaler"]
    assert np.allclose(np.array(artifact["coef"]), classifier.coef_, atol=1e-12)
    assert np.allclose(np.array(artifact["intercept"]), classifier.intercept_, atol=1e-12)
    assert np.allclose(np.array(artifact["scaler_mean"]), scaler.mean_, atol=1e-12)
    assert np.allclose(np.array(artifact["scaler_scale"]), scaler.scale_, atol=1e-12)


def test_sklearn_and_served_probabilities_agree_over_the_complete_dataset(
        artifact, dataset, refit):
    """Every row, not spot checks — the same bar DEV-97 sets for the neural path.

    The artifact's temperature is applied to the sklearn side, because the serving
    path divides its logits by it (DEV-88) and the shipped value is 1.05, not 1.0.
    Comparing against untempered sklearn output would fail here for a reason that
    has nothing to do with parity.
    """
    _, careers, X, _ = dataset
    expected = tempered_reference(refit, X, artifact["temperature"])
    actual = served(MatcherModel(artifact), X, careers)
    assert np.abs(expected - actual).max() < PARITY_TOLERANCE


def test_on_the_real_data_that_reference_is_the_offline_calibration_one(artifact, dataset, refit):
    """Ties the logit-space reference back to the function the temperature was
    actually fitted with, where they agree — so using it above is not a quiet
    redefinition of what `temperature` means."""
    _, _, X, _ = dataset
    logit_space = tempered_reference(refit, X, artifact["temperature"])
    probability_space = apply_temperature(refit.predict_proba(X), artifact["temperature"])
    assert np.abs(logit_space - probability_space).max() < PARITY_TOLERANCE


def test_parity_holds_on_randomized_vectors(artifact, dataset, refit):
    """Off-distribution inputs, so parity is not an artifact of the training rows."""
    _, careers, X, _ = dataset
    rng = np.random.default_rng(20260803)
    R = rng.uniform(-3.0, 3.0, size=(200, X.shape[1]))
    expected = tempered_reference(refit, R, artifact["temperature"])
    actual = served(MatcherModel(artifact), R, careers)
    assert np.abs(expected - actual).max() < PARITY_TOLERANCE


def test_the_served_temperature_is_not_inert(artifact, dataset, refit):
    """A guard against this file passing vacuously.

    If the shipped temperature were 1.0, the test above would hold whether or not
    the serving path applied it at all. It is 1.05, and this pins that the
    difference is real and large enough to matter to a displayed percentage.
    """
    _, careers, X, _ = dataset
    assert artifact["temperature"] != 1.0
    untempered = refit.predict_proba(X)
    actual = served(MatcherModel(artifact), X, careers)
    assert np.abs(untempered - actual).max() > 1e-3
