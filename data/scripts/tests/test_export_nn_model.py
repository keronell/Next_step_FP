"""`export_nn_model.py`: the ship-floor branch, the fold, and torch-vs-numpy parity.

Run from repo root with the TRAINING venv (this module needs torch; `Scripts/`
replaces `bin/` on Windows, as everywhere in data/scripts/README.md):

    data/venv-training/bin/python -m pytest data/scripts/tests -q

Under the service-test venv it skips whole, like every other torch-dependent module
here.

## Why the parity tests live in this file rather than under services/matching/tests

They need **both** runtimes in one process: torch, which only the training venv has,
and `app.services.matcher_nn.NeuralMatcher`, which lives under `services/matching`.
Only this venv can have both, so this is the only place the comparison can be made
live rather than against a recorded snapshot.

The tempting alternative — reimplementing the numpy forward pass here to dodge the
import — would make the test compare two copies of the same code and pass while
proving nothing, which is precisely the failure DEV-97 exists to prevent. So the
real serving class is imported, through the same `sys.path` insertion
`export_nn_model` itself makes.

That import needs one shim, and it is disclosed rather than hidden: `matcher_nn`
imports `common.logging`, which reaches `common.config` and therefore
`pydantic_settings`, which the training venv does not have and must not gain — it is
hash-pinned and the dataset digest depends on it. `common.config` is stubbed to a
log level and nothing else. **The code under test is byte-identical**; only the
logging configuration it never exercises here is replaced.
"""
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "data" / "scripts"))

np = pytest.importorskip("numpy")
pytest.importorskip("torch")
pytest.importorskip("sklearn")
pytest.importorskip("pandas")

import pandas as pd  # noqa: E402
import torch  # noqa: E402

# The stub goes in before matcher_nn is imported; see the module docstring.
if "common.config" not in sys.modules:
    _stub = types.ModuleType("common.config")
    _stub.get_settings = lambda: types.SimpleNamespace(log_level="INFO")
    sys.modules["common.config"] = _stub

sys.path[:0] = [str(REPO_ROOT / "services"), str(REPO_ROOT / "services" / "matching")]

import export_nn_model as ex  # noqa: E402
from app.services.matcher_nn import NeuralMatcher  # noqa: E402
from nn_model import SeedEnsemble  # noqa: E402
from train_models import apply_temperature  # noqa: E402

TRAINING_DIR = REPO_ROOT / "data" / "training"

#: Agreement required between the torch model and the numpy serving path.
#:
#: Chosen from what the runtimes can differ by, not from what happened to pass.
#: `NNClassifier` computes in float32 (eps ~1.2e-7) and `NeuralMatcher` in float64,
#: so three layers of accumulation put the floor around 1e-6. The measured maximum
#: over every check in this file is ~4.7e-7.
#:
#: It is also deliberately far below the defect it has to catch: exporting the
#: constant features naively instead of folding them (see
#: `export_nn_model.fold_constant_features`) diverged by 1.0e-2, five orders of
#: magnitude above this bar.
PARITY_TOLERANCE = 1e-5


# ------------------------------------------------------------------- fixtures
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
def spec():
    return json.loads(
        (TRAINING_DIR / "round2_results.json").read_text(encoding="utf-8")
    )["selected_specification"]


@pytest.fixture(scope="module")
def fitted(dataset, spec):
    """The exported configuration, fitted on all rows — the same call `main()` makes.

    Module-scoped: this is ~8 seconds of torch, and every parity test wants the same
    five members.
    """
    _, _, X, y = dataset
    ensemble, _ = ex.build_estimator(spec)
    return ensemble.fit(X, y)


@pytest.fixture(scope="module")
def exported(fitted, dataset):
    feature_names, careers, X, _ = dataset
    members, mean, scale = ex.serialize_members(fitted, X)
    return {
        "model_type": ex.MODEL_TYPE,
        "feature_version": json.loads(
            (TRAINING_DIR / "dataset_metadata.json").read_text(encoding="utf-8")
        )["feature_version"],
        "feature_names": feature_names,
        "careers": careers,
        "scaler_mean": mean,
        "scaler_scale": scale,
        "activation": "relu",
        "members": members,
        "caveats": [],
    }


def probabilities(matcher: NeuralMatcher, X, careers) -> np.ndarray:
    return np.array([[matcher.predict_proba(list(row))[c] for c in careers] for row in X])


# ------------------------------------------------- the split ship floor (ADR 0002)
def test_a_stability_failure_refuses_to_write():
    """The hard half. ADR 0002 gives it no mitigation, so there is no branch in
    which an unstable model reaches an artifact."""
    decision = ex.gate1_decision(ece=0.02, stability=0.55, max_ece=0.10, min_stability=0.60)
    assert decision["may_write"] is False
    assert decision["status"] == "refused"


def test_an_ece_failure_writes_and_records_the_mitigation():
    """The mitigable half, and the reason this exporter is not a copy of the linear
    one: the selected configuration lands exactly here, so a flat reading of
    "refuse when Gate 1 fails" would refuse the model the project has decided to
    ship."""
    decision = ex.gate1_decision(ece=0.1392, stability=0.7346, max_ece=0.10, min_stability=0.60)
    assert decision["may_write"] is True
    assert decision["status"] == "ranking_only"
    assert decision["ece_clears"] is False
    assert decision["stability_clears"] is True


def test_clearing_both_floors_is_a_distinct_status():
    decision = ex.gate1_decision(ece=0.03, stability=0.75, max_ece=0.10, min_stability=0.60)
    assert decision["status"] == "ranking_and_percentages"


def test_the_status_is_never_a_bare_boolean():
    """A consumer reading `deployable: true` would reasonably infer the percentages
    are calibrated. For the shipped configuration they are not, so the artifact
    reports which of the two it earned and never a yes/no."""
    for status in ("refused", "ranking_only", "ranking_and_percentages"):
        assert not isinstance(status, bool)
    decision = ex.gate1_decision(0.1392, 0.7346, 0.10, 0.60)
    assert "deployable" not in decision


def test_the_calibration_caveat_appears_only_when_ece_fails():
    failing = ex.calibration_caveat(ex.gate1_decision(0.1392, 0.7346, 0.10, 0.60))
    assert len(failing) == 1
    assert "NOT calibrated" in failing[0]
    # The mitigation has to name what to do, not merely that something is wrong.
    assert "FALL BACK" in failing[0].upper()
    assert ex.calibration_caveat(ex.gate1_decision(0.03, 0.75, 0.10, 0.60)) == []


def test_the_calibration_caveat_reaches_the_artifact_caveats(dataset):
    """`caveats` travel inside the artifact to the recommendations response, the
    persisted history and the results UI — that is the whole delivery mechanism for
    the mitigation."""
    _, careers, _, _ = dataset
    df = pd.read_parquet(TRAINING_DIR / "train_features.parquet")
    decision = ex.gate1_decision(0.1392, 0.7346, 0.10, 0.60)
    caveats = ex.build_caveats(df, careers, decision)
    assert any("NOT calibrated" in c for c in caveats)
    # And the circularity caveat is carried identically to the linear exporter's.
    assert any("bank-consistent" in c for c in caveats)


# ------------------------------------------------------ configuration reconstruction
def test_the_estimator_is_rebuilt_from_the_recorded_specification(spec):
    ensemble, unrecorded = ex.build_estimator(spec)
    assert isinstance(ensemble, SeedEnsemble)
    assert ensemble.n_members == spec["n_members"]
    assert ensemble.random_state == spec["random_state"]
    assert ensemble.member_kwargs["dropout"] == spec["member"]["dropout"]
    assert ensemble.member_kwargs["weight_decay"] == spec["member"]["weight_decay"]
    # `val_size` postdates the record (DEV-96). Reported, not silently absorbed.
    assert unrecorded == ["val_size"]


def test_a_specification_naming_another_architecture_is_refused(spec):
    with pytest.raises(SystemExit, match="SeedEnsemble"):
        ex.build_estimator({**spec, "class": "nn_model.ResidualMatcher"})


def test_a_specification_with_unbuildable_hyperparameters_is_refused(spec):
    """Refuse rather than drop: a hyperparameter the constructor no longer accepts
    means the record and the code have diverged, and the model that was selected can
    no longer be rebuilt."""
    broken = {**spec, "member": {**spec["member"], "nonexistent_knob": 3}}
    with pytest.raises(SystemExit, match="no longer accepts"):
        ex.build_estimator(broken)


# ------------------------------------------------------------ the constant-feature fold
def test_the_real_dataset_has_constant_features(dataset):
    """The fold is not hypothetical — it fires on the shipped dataset. If this ever
    stops being true, the fold becomes dead code and should be re-read, not deleted
    on the assumption it never mattered."""
    _, _, X, _ = dataset
    assert int(ex.constant_feature_mask(X).sum()) == 5


def test_constant_features_standardize_to_a_nonzero_constant_in_training(dataset, fitted):
    """The counter-intuitive fact the fold exists for: `scale_ = std + 1e-8` does
    NOT make a constant column standardize to zero, because the float32 mean of 232
    values carries rounding. `game-dev_skill` is 0.8 in every row and reaches the
    network as roughly -0.92."""
    feature_names, _, X, _ = dataset
    member = fitted.members_[0]
    standardized = ex.training_standardized(X, member.mean_, member.scale_)
    j = feature_names.index("game-dev_skill")
    assert len(np.unique(X[:, j])) == 1
    assert abs(standardized[0, j]) > 0.5


def test_folding_leaves_the_composed_function_unchanged(dataset, fitted, exported):
    """The fold moves a constant from the input to the bias, so the network's output
    must not move at all — this is what makes it a re-encoding rather than a change
    to the model."""
    _, careers, X, _ = dataset
    served = probabilities(NeuralMatcher({**exported, "temperature": 1.0}), X, careers)
    assert np.abs(fitted.predict_proba(X) - served).max() < PARITY_TOLERANCE


def test_folded_features_are_pinned_and_carry_no_weight(dataset, exported):
    feature_names, _, X, _ = dataset
    constant = ex.constant_feature_mask(X)
    scale = np.array(exported["scaler_scale"])
    assert np.all(scale[constant] == 0.0)
    assert np.all(scale[~constant] > 0.0)
    first_layer = np.array(exported["members"][0]["layers"][0]["weight"])
    assert np.all(first_layer[:, constant] == 0.0), (
        "a weight on a pinned input can never fire and would mislead a reader"
    )
    assert np.any(first_layer[:, ~constant] != 0.0)


def test_a_member_with_a_divergent_scaler_is_refused(fitted, dataset):
    """One shared scaler is only correct because the members see the identical
    training matrix. If that stopped holding, four members out of five would be
    silently misstandardized."""
    _, _, X, _ = dataset

    class _Divergent:
        def __init__(self, members):
            self.members_ = members

    tampered = [fitted.members_[0], _Tampered(fitted.members_[1])]
    with pytest.raises(SystemExit, match="different statistics"):
        ex.serialize_members(_Divergent(tampered), X)


class _Tampered:
    """A member whose scaler disagrees, without mutating the shared fitted one."""

    def __init__(self, member):
        self.mean_ = member.mean_ + 1.0
        self.scale_ = member.scale_
        self.model_ = member.model_


# ------------------------------------------------------------------------ parity
def test_per_member_parity_over_the_complete_dataset(dataset, fitted, exported):
    """Every member, every row — not spot checks.

    Per-member as well as ensemble-level, because the averaging step is where a
    member-ordering or seed-mapping mistake hides: five members that are
    individually right but mapped to the wrong seeds still average to something
    plausible, and a check on the average alone would pass.
    """
    _, careers, X, _ = dataset
    for i, member in enumerate(fitted.members_):
        single = NeuralMatcher({**exported, "members": [exported["members"][i]],
                                "temperature": 1.0})
        worst = np.abs(member.predict_proba(X) - probabilities(single, X, careers)).max()
        assert worst < PARITY_TOLERANCE, f"member {i} diverges by {worst:.3e}"


def test_per_member_logit_parity_over_the_complete_dataset(dataset, fitted, exported):
    """The spec asks for logits *and* probabilities, and they are not the same claim.

    Softmax is invariant to a shared additive shift, so probability parity would
    still hold if every logit in a row were off by the same constant. Logits are also
    the quantity DEV-94's attribution is expressed in, so a drift the softmax hides
    would surface in the reasons rather than in the percentages.

    Compared per member, since the ensemble has no logits of its own — it averages
    probabilities, and the thing `matcher_nn` calls a logit is the log of that
    average.
    """
    _, _, X, _ = dataset
    Z = np.array([NeuralMatcher({**exported, "temperature": 1.0})._scaled(list(row))
                  for row in X])
    for i, member in enumerate(fitted.members_):
        weights = [(np.array(layer["weight"]), np.array(layer["bias"]))
                   for layer in exported["members"][i]["layers"]]
        h = Z
        for depth, (w, b) in enumerate(weights):
            h = h @ w.T + b
            if depth < len(weights) - 1:
                h = np.maximum(h, 0.0)
        expected = member._mlp_output(X).numpy().astype(np.float64)
        # Logits are unbounded, so an absolute bar would be a different (and weaker)
        # claim on a row whose logits are large. Scaled by the spread being explained.
        worst = np.abs(expected - h).max() / max(np.abs(expected).max(), 1.0)
        assert worst < PARITY_TOLERANCE, f"member {i} logits diverge by {worst:.3e}"


def test_ensemble_parity_over_the_complete_dataset(dataset, fitted, exported):
    _, careers, X, _ = dataset
    served = probabilities(NeuralMatcher({**exported, "temperature": 1.0}), X, careers)
    assert np.abs(fitted.predict_proba(X) - served).max() < PARITY_TOLERANCE


def test_member_order_is_not_scrambled(dataset, fitted, exported):
    """Each serialized member must match the torch member at the SAME index and
    disagree with the others.

    Without the second half a permutation of the five would pass every other parity
    test in this file, since the ensemble average is order-invariant.
    """
    _, careers, X, _ = dataset
    rows = X[:12]
    served = [probabilities(NeuralMatcher({**exported, "members": [m], "temperature": 1.0}),
                            rows, careers)
              for m in exported["members"]]
    for i, member in enumerate(fitted.members_):
        reference = member.predict_proba(rows)
        assert np.abs(reference - served[i]).max() < PARITY_TOLERANCE
        for k in range(len(served)):
            if k != i:
                assert np.abs(reference - served[k]).max() > PARITY_TOLERANCE, (
                    f"torch member {i} is indistinguishable from serialized member {k} - "
                    "member identity cannot be verified, so an ordering error would hide"
                )


def test_parity_on_randomized_vectors(dataset, fitted, exported):
    """Off-distribution inputs, so parity is not an artifact of the training rows.

    The columns that were constant in training are held at their training value.
    Varying them would not test the runtimes against each other — it would compare
    two different extrapolations of a feature the model has no information about,
    where torch's ~1e7 standardization slope makes any disagreement meaningless.
    """
    _, careers, X, _ = dataset
    constant = ex.constant_feature_mask(X)
    rng = np.random.default_rng(20260803)
    R = rng.uniform(-3.0, 3.0, size=(200, X.shape[1]))
    R[:, constant] = X[0, constant]
    served = probabilities(NeuralMatcher({**exported, "temperature": 1.0}), R, careers)
    assert np.abs(fitted.predict_proba(R) - served).max() < PARITY_TOLERANCE


def test_serving_applies_temperature_the_way_the_offline_fit_did(dataset, fitted, exported):
    """`matcher_nn` divides the log of the averaged probabilities by T and
    renormalizes, which is `train_models.apply_temperature` exactly. That identity
    is what makes the deployment temperature transferable at all."""
    _, careers, X, _ = dataset
    T = 0.8
    served = probabilities(NeuralMatcher({**exported, "temperature": T}), X, careers)
    expected = apply_temperature(fitted.predict_proba(X), T)
    assert np.abs(expected - served).max() < PARITY_TOLERANCE


# ------------------------------------------------------------- the shipped artifact
def test_the_shipped_artifact_is_the_model_that_was_evaluated(exported):
    """The committed artifact must be reproducible from the recorded specification.

    If it is not, every number in the decision document describes something that
    never ships — which is the failure this ticket's parity work exists to rule out.
    """
    artifact = json.loads(ex.OUT_PATH.read_text(encoding="utf-8"))
    assert artifact["members"] == exported["members"]
    assert artifact["scaler_mean"] == exported["scaler_mean"]
    assert artifact["scaler_scale"] == exported["scaler_scale"]


def test_the_shipped_artifact_records_the_split_floor_verdict():
    artifact = json.loads(ex.OUT_PATH.read_text(encoding="utf-8"))
    gate1 = artifact["selection"]["exported_config_gate1"]
    assert gate1["stability_clears"] is True
    assert gate1["ece_clears"] is False
    assert artifact["deployment"]["status"] == "ranking_only"
    assert "FALL BACK" in artifact["deployment"]["match_percent"].upper()
    assert any("NOT calibrated" in c for c in artifact["caveats"])


def test_the_shipped_artifact_loads_through_the_serving_factory():
    """Round-trip through the real dispatch seam, not a direct construction — the
    artifact has to satisfy `load_matcher`'s validation, not merely resemble it."""
    from app.services.matcher import load_matcher

    matcher = load_matcher(ex.OUT_PATH)
    assert isinstance(matcher, NeuralMatcher)
    assert matcher.version == ex.MODEL_VERSION
    assert len(matcher.members) == 5
    assert matcher.temperature > 0
    assert any("NOT calibrated" in c for c in matcher.caveats)
