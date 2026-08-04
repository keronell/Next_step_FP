"""Export the selected neural matcher as a serving artifact (DEV-23 Step 5.2 / DEV-97).

The neural sibling of `export_model.py`. Reconstructs the configuration DEV-95
selected, revalidates *that exact configuration* against the Gate-1 thresholds,
fits a deployment temperature, and writes a dependency-free JSON artifact that
`services/matching/app/services/matcher.py::load_matcher` dispatches on. No pickle,
no torch at serve time.

Output: data/models/matcher_nn_v1.json
Run from repo root with the TRAINING venv (this needs torch):

    data/venv-training/bin/python data/scripts/export_nn_model.py

## The configuration is read, never retyped

`selected_specification` in `round2_results.json` is generated from
`inspect.signature`, precisely so it cannot drift from the constructor. This script
reconstructs from that record and then *proves* the reconstruction faithful by
reproducing the recorded ship floor to `SHIP_FLOOR_TOLERANCE`. A signature-level
audit would not have caught a changed default that still type-checks; reproducing
the two recorded numbers does.

## Gate 1 is one gate with two halves, and they are not equally negotiable

ADR 0005 splits the ship floor deliberately, and this exporter honours the split
rather than the flat reading of DEV-97's acceptance criterion:

- **Top-2 stability >= 0.60 is hard and unmitigable.** Failing it means the same
  user gets different recommendations depending on which resample trained the
  model, and the ranking *is* the product. This script refuses to write.
- **ECE <= 0.10 has a defined mitigation.** It matters only because `Results.jsx`
  renders `matchPercent`, so a model failing it may still ship as the *ranking*
  source with displayed percentages falling back to the formula's. This script
  writes, and records the failure and the mitigation inside the artifact and in
  `caveats` — which travel to the recommendations response, the persisted history
  and the results UI.

The selected configuration is expected to take exactly that second branch
(`ship_floor` in `round2_results.json`: stability 0.735 clears, ECE 0.139 fails).
Refusing there would refuse to write the model the project has decided to ship, so
the artifact deliberately carries no bare `deployable: true` a consumer could read
as "the percentages are calibrated" — `deployment.status` names which of the two it
earned.

## What the temperature is, and what it is not

`temperature` here is a **deployment** constant: `fit_temperature` on pooled OOF
probabilities from the exact configuration serialized below. That is the first of
the two same-pool uses `train_models.temperature_scale`'s docstring still calls
honest, and it is consistent with ADR 0007, which removes same-pool fitting from
*reported* metrics rather than from the choice of one shipped constant. It is
**not** the per-outer-fold cross-fitted temperature that ADR 0007 requires for a
reported ECE; that one stays per-fold and is not touched here.

Those OOF probabilities are **ensemble-averaged** — `SeedEnsemble.predict_proba`,
the mean of the members' probabilities. That is forced by DEV-94: the serving path
explains `g_c = log(mean_i softmax(z_i)_c) / T`, so T has to be fitted on the
quantity that logit is taken of. Fitting on mean-of-logits would put T somewhere no
offline fit ever put it, and the shipped explanation would describe a model nobody
serves.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
# Same insertion export_model.py makes, and for the same reason: services/ provides
# the `common` package and services/matching the `app` package.
sys.path.insert(0, str(REPO_ROOT / "services"))
sys.path.insert(0, str(REPO_ROOT / "services" / "matching"))

from dataset_guards import dataset_caveats, dataset_digest  # noqa: E402

from app.services.feature_builder import FEATURE_VERSION  # noqa: E402

TRAINING_DIR = REPO_ROOT / "data" / "training"
ROUND2_RESULTS = TRAINING_DIR / "round2_results.json"
OUT_PATH = REPO_ROOT / "data" / "models" / "matcher_nn_v1.json"

MODEL_VERSION = "matcher-nn-v1"
MODEL_TYPE = "probability_averaged_mlp_ensemble"

#: How far the revalidated ship floor may sit from the one DEV-95 recorded before
#: this script refuses. Reproducing those two numbers is what proves the
#: reconstruction from `selected_specification` is the configuration that was
#: selected, so the tolerance is tight enough to catch a changed default and loose
#: enough to survive float non-associativity across a torch patch release.
SHIP_FLOOR_TOLERANCE = 1e-6


class ExportError(SystemExit):
    """Refusal to write. `SystemExit` so an unhandled one still ends the process
    with a message rather than a traceback, matching export_model.py's posture."""


# --------------------------------------------------------------- configuration
def build_estimator(spec: dict):
    """Reconstruct the selected estimator from `selected_specification`.

    Every recorded member hyperparameter is passed **explicitly**, including the
    ones that merely restate a default. That is the drift-proof direction: the
    artifact then reproduces the values DEV-95 recorded rather than whatever
    `nn_model`'s defaults happen to be today.

    A parameter the constructor has but the record does not (the record predates
    `val_size`, added by DEV-96's learning curve) falls back to today's default and
    is returned in `unrecorded` so the caller can report it. It is not fatal on its
    own — the ship-floor reproduction is what decides whether it mattered.
    """
    import inspect

    from nn_model import NNClassifier, SeedEnsemble

    if spec.get("class") != "nn_model.SeedEnsemble":
        raise ExportError(
            f"selected_specification names {spec.get('class')!r}, but this exporter "
            f"produces {MODEL_TYPE!r} artifacts, which serve a SeedEnsemble of MLPs. "
            "Build a serving path for that architecture before exporting it."
        )
    member = dict(spec["member"])
    if member.pop("class", None) != "nn_model.NNClassifier":
        raise ExportError(
            "selected_specification's member is not an nn_model.NNClassifier - the "
            "numpy serving path implements a plain ReLU MLP and nothing else."
        )

    accepted = {
        name for name, p in inspect.signature(NNClassifier.__init__).parameters.items()
        if p.default is not inspect.Parameter.empty
    }
    unknown = sorted(set(member) - accepted)
    if unknown:
        raise ExportError(
            f"selected_specification records member hyperparameters {unknown} that "
            "nn_model.NNClassifier no longer accepts - the record and the constructor "
            "have diverged; do not export a configuration that cannot be rebuilt."
        )
    unrecorded = sorted(accepted - set(member))

    ensemble = SeedEnsemble(
        random_state=spec["random_state"], n_members=spec["n_members"], **member
    )
    return ensemble, unrecorded


# ------------------------------------------------------------- Gate-1 decision
def gate1_decision(ece: float, stability: float, max_ece: float,
                   min_stability: float) -> dict:
    """Which half of ADR 0005's split ship floor this configuration earned.

    Pure, so the branch that decides whether a model may ship is testable without a
    three-minute fit. `status` is a string and never a bare boolean: a consumer who
    sees `deployable: true` would reasonably infer the percentages are calibrated,
    and for the selected configuration they are not.
    """
    ece_clears = bool(ece <= max_ece)
    stability_clears = bool(stability >= min_stability)
    return {
        "ece": float(ece),
        "ece_floor": max_ece,
        "ece_clears": ece_clears,
        "top2_stability": float(stability),
        "stability_floor": min_stability,
        "stability_clears": stability_clears,
        "may_write": stability_clears,
        "status": (
            "ranking_and_percentages" if ece_clears and stability_clears
            else "ranking_only" if stability_clears
            else "refused"
        ),
    }


def calibration_caveat(decision: dict) -> list[str]:
    """The mitigation, in the one place that reaches the user.

    `caveats` travel inside the artifact to the recommendations response, the
    persisted history and the results UI, so this is what stops a served percentage
    from silently claiming a calibration the model does not have.
    """
    if decision["ece_clears"]:
        return []
    return [
        "Displayed match percentages from this model are NOT calibrated: its pooled "
        f"out-of-fold ECE is {decision['ece']:.3f}, above the {decision['ece_floor']} "
        "ship floor. Under ADR 0005 that floor is mitigable rather than hard, so this "
        "model ships as the RANKING source only and displayed percentages should fall "
        "back to the formula's. The ordering of recommendations is gated separately, "
        f"on top-2 stability ({decision['top2_stability']:.3f} against a "
        f"{decision['stability_floor']} floor), and clears."
    ]


# ------------------------------------------------------------- serialization
def constant_feature_mask(X: np.ndarray) -> np.ndarray:
    """Columns that never varied in training.

    These are the columns whose standardization cannot survive the change of dtype
    between training and serving, and they need folding rather than copying — see
    `fold_constant_features`. Exact constancy is the condition, deliberately, rather
    than a near-constant threshold: a threshold would be an invented policy with a
    tuned constant in it. Anything near-constant-but-not-constant is left alone and
    is caught by the parity tests' tolerance instead of being silently rounded away.
    """
    # float32, not float64. What triggers the pathology is `X.std()` collapsing to
    # ~0 in the dtype the estimator standardizes in, so a column that varies only
    # below float32 resolution is degenerate for this purpose even though float64
    # can still tell its values apart. Testing in float64 would leave exactly that
    # column unfolded and pathological.
    X32 = X.astype(np.float32)
    return X32.max(axis=0) == X32.min(axis=0)


def training_standardized(X: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """The standardized matrix `NNClassifier._mlp_output` actually computes.

    Reproduced rather than approximated, because the dtype is the whole point. Both
    the cast and the arithmetic must match `nn_model.py`'s
    `(np.asarray(X, dtype=np.float32) - self.mean_) / self.scale_`: the cast happens
    **before** the subtraction, and `mean_`/`scale_` are float32, so the whole
    expression evaluates in float32. Widening `scale` first would leave the division
    in float64 and shift the recovered constant by ~1e-7 relative — small, but this
    function's only job is to be exact.
    """
    return (X.astype(np.float32) - np.asarray(mean, dtype=np.float32)
            ) / np.asarray(scale, dtype=np.float32)


def fold_constant_features(members: list[dict], X: np.ndarray,
                           mean: np.ndarray, scale: np.ndarray) -> tuple[list[dict], np.ndarray]:
    """Move each constant feature's fixed contribution from the input into the bias.

    **The bug this exists to prevent, stated exactly, because the intuitive version
    of it is wrong.** `NNClassifier` standardizes with `scale_ = X.std(axis=0) +
    1e-8`, so a column that never varied gets a scale of ~1e-8 instead of a zero it
    could branch on. The tempting conclusion is that such a column standardizes to
    0.0 and is therefore inert. It does not. `mean_` is the **float32 mean of 232
    values**, and that accumulates rounding: for `game-dev_skill` the column is
    0.8 everywhere, `float32(0.8) = 0.800000011920929`, but the computed mean is
    `0.8000001311302185`. The residual is -1.19e-7 and the scale is 1.29e-7, so
    training fed the network a constant **-0.9226** on that input — an O(1) value,
    not a zero. The network absorbed it as an extra bias.

    Serving cannot reproduce that by copying the numbers across, because
    `matcher_nn` evaluates `(x - mean) / scale` in float64 and gets **-1.0149** for
    the same feature: a different constant. Measured end to end, copying moved
    served probabilities by up to 1.0e-2, while the network forward pass itself
    agrees to 1.6e-6.

    So the constant is folded where it belongs. For each constant column `j` with
    training-standardized value `v_j`, the first layer's bias absorbs
    `W[:, j] * v_j` and `W[:, j]` becomes zero; the exporter then emits `scale = 0`
    for `j`, which is the case `matcher_nn` already branches on (`_live`) and maps
    to exactly 0.0. The composed function then matches training's **for every
    input**, to the float32 precision `v_j` itself was computed at, and the ~1e7
    amplification is gone from the serving path rather than compensated for.

    Zeroing the weight is not cosmetic. Left in place it could never fire (its input
    is pinned to 0.0), so it would be a trap for anyone reading the artifact — and
    it would invite an attribution for a feature that demonstrably carries no
    information, since it never varied.
    """
    constant = constant_feature_mask(X)
    if not constant.any():
        return members, scale
    standardized = training_standardized(X, mean, scale)
    values = standardized[0].astype(np.float64)
    # Constant in, constant out — asserted, since the fold is only exact if every
    # row really does standardize to the same number.
    if not np.array_equal(standardized[:, constant], np.broadcast_to(
            standardized[0, constant], standardized[:, constant].shape)):
        raise ExportError(
            "a column that is constant in the feature matrix did not standardize to "
            "a constant, so folding it into the bias would not be exact"
        )

    folded = []
    for member in members:
        layers = [{"weight": [row[:] for row in layer["weight"]], "bias": layer["bias"][:]}
                  for layer in member["layers"]]
        weight = np.array(layers[0]["weight"], dtype=np.float64)
        bias = np.array(layers[0]["bias"], dtype=np.float64)
        bias += weight[:, constant] @ values[constant]
        weight[:, constant] = 0.0
        layers[0]["weight"] = weight.tolist()
        layers[0]["bias"] = bias.tolist()
        folded.append({"layers": layers})

    scale = scale.copy()
    scale[constant] = 0.0
    return folded, scale


def serialize_members(ensemble, X: np.ndarray) -> tuple[list[dict], list[float], list[float]]:
    """Members' layer stacks plus the ONE scaler they share.

    Each `NNClassifier` fits its own `mean_`/`scale_`, but every member of a
    `SeedEnsemble` sees the identical training matrix, so the five are five copies of
    one thing and the artifact stores it once. That is checked here rather than
    assumed: if it ever stopped holding, a single shared scaler would silently
    misstandardize four members out of five.

    `nn.Linear.weight` is already (out_features, in_features) — the same convention
    as the linear artifact's `coef` — so the layers transfer without a transpose.
    """
    import torch

    reference = ensemble.members_[0]
    for i, m in enumerate(ensemble.members_[1:], start=1):
        if not (np.array_equal(reference.mean_, m.mean_)
                and np.array_equal(reference.scale_, m.scale_)):
            raise ExportError(
                f"ensemble member {i} standardizes on different statistics than member "
                "0, so the artifact's single shared scaler would be wrong for it. "
                "SeedEnsemble members are supposed to differ only in seed."
            )

    members = []
    for m in ensemble.members_:
        layers = [
            {"weight": layer.weight.detach().numpy().astype(float).tolist(),
             "bias": layer.bias.detach().numpy().astype(float).tolist()}
            for layer in m.model_.net if isinstance(layer, torch.nn.Linear)
        ]
        if not layers:
            raise ExportError("a member exposed no nn.Linear layers to serialize")
        members.append({"layers": layers})

    # float32 in torch, float64 in the artifact. Widening is exact, so on every
    # column with a real scale the served standardization consumes the same numbers
    # the training pass did. The constant columns are the exception and are folded
    # into the first layer's bias instead — see fold_constant_features.
    members, scale = fold_constant_features(
        members, X, reference.mean_, reference.scale_.astype(np.float64)
    )
    return members, reference.mean_.astype(float).tolist(), scale.tolist()


def build_caveats(df: pd.DataFrame, careers: list[str], decision: dict) -> list[str]:
    """Circularity caveat + class-balance caveats + the calibration mitigation.

    The first two are carried identically to `export_model.build_caveats` — the
    circularity one is a property of the labeling protocol and applies to any model
    trained on these labels, neural or linear.
    """
    return [
        "Labels are bank-consistent, not independently validated: silver labels come "
        "from an LLM panel whose stage-2 vote follows the answer key derived from "
        "careers.json bonuses ~94% of the time it speaks. Panel-agreement metrics "
        "measure fidelity to the hand-authored bonus table, not real-world accuracy.",
        *dataset_caveats(df["label_top1"], careers),
        *calibration_caveat(decision),
    ]


def main() -> None:
    df = pd.read_parquet(TRAINING_DIR / "train_features.parquet")
    meta = json.loads((TRAINING_DIR / "dataset_metadata.json").read_text(encoding="utf-8"))
    feature_names = meta["feature_names"]
    careers = [n[: -len("_fit")] for n in feature_names if n.endswith("_fit")]
    if meta["feature_version"] != FEATURE_VERSION:
        raise ExportError("dataset feature_version != code FEATURE_VERSION - rebuild the dataset")

    if not ROUND2_RESULTS.exists():
        raise ExportError(f"{ROUND2_RESULTS} not found - run sweep_round2.py (DEV-95) first.")
    round2 = json.loads(ROUND2_RESULTS.read_text(encoding="utf-8"))

    # The selection must have been computed on THIS dataset content, for the reason
    # export_model.py gives: the digest hashes the loaded features+labels, so a
    # regenerated or hand-edited parquet cannot be paired with an obsolete selection.
    current_digest = dataset_digest(df, feature_names)
    if round2.get("dataset_digest") != current_digest:
        raise ExportError(
            "round2_results.json was produced for different dataset content "
            f"(digest {round2.get('dataset_digest')!r} vs current {current_digest!r}) - "
            "rerun the sweep on the current train_features.parquet first."
        )

    spec = round2.get("selected_specification")
    if not spec:
        raise ExportError(
            "round2_results.json records no selected_specification - it predates "
            "DEV-95's selection; nothing may be exported."
        )
    recorded_floor = round2.get("ship_floor") or {}
    if recorded_floor.get("configuration") != round2.get("selected_variant"):
        raise ExportError(
            f"round2_results.json's ship floor was measured for "
            f"{recorded_floor.get('configuration')!r} but the selected variant is "
            f"{round2.get('selected_variant')!r} - Gate-1 qualification is a property "
            "of one exact configuration and does not transfer."
        )

    _, unrecorded = build_estimator(spec)
    if unrecorded:
        print(f"note: {unrecorded} are not in selected_specification (it predates them); "
              "falling back to the constructor default and proving it inert by "
              "reproducing the recorded ship floor below.")

    X = df[feature_names].to_numpy(dtype=float)
    y = df["label_top1"].map({c: i for i, c in enumerate(careers)}).to_numpy()

    import evaluate_matchers as em
    from train_models import fit_temperature

    # Every estimator built from here on comes through `build_estimator`, so the
    # configuration that is revalidated and the one that is serialized are the same
    # construction, behind the same guards. Reconstructing the kwargs separately
    # here would put the unchecked copy on the path that actually ships.
    def factory():
        return build_estimator(spec)[0]

    # Gate-1 revalidation of the EXACT exported configuration, on the protocol
    # sweep_variants.evaluate_ship_floor used, at the seed it used. The determinism
    # assertion is not optional and not merely ordered-by-convention: an estimator
    # whose refits disagree would have its own randomness read as training-subset
    # variation, and the hard floor could fire on a measurement artifact.
    print(f"revalidating {round2['selected_variant']} against the Gate-1 thresholds "
          f"(this fits {5 * 4} ensembles; ~3 minutes)...")
    em.assert_deterministic(round2["selected_variant"], factory, X, y)
    oof, stability = em.cv_oof_and_stability(
        X, y, factory, len(careers), random_state=spec["random_state"]
    )
    ece = float(em.rank_metrics(oof, y, oof, len(careers))["ece"])

    # Faithfulness of the reconstruction, proved rather than argued: these two
    # numbers are what `selected_specification` plus this protocol produced for
    # DEV-95, so reproducing them is what rules out a silently changed default.
    drift = {
        "ece": abs(ece - recorded_floor["ece"]),
        "top2_stability": abs(stability - recorded_floor["top2_stability"]),
    }
    if max(drift.values()) > SHIP_FLOOR_TOLERANCE:
        raise ExportError(
            "the reconstructed configuration does not reproduce the ship floor "
            f"DEV-95 recorded: ECE {ece!r} vs {recorded_floor['ece']!r}, top-2 "
            f"stability {stability!r} vs {recorded_floor['top2_stability']!r} "
            f"(drift {drift}, tolerance {SHIP_FLOOR_TOLERANCE}). Either "
            "selected_specification no longer rebuilds the model that was selected, "
            "or the environment moved. Do not export a model whose provenance record "
            "describes something else."
        )
    print(f"reproduced the DEV-95 ship floor (max drift {max(drift.values()):.3g}).")

    decision = gate1_decision(ece, stability, em.GATE1_MAX_ECE, em.GATE1_MIN_TOP2_STABILITY)
    if not decision["may_write"]:
        raise ExportError(
            f"exported configuration violates the HARD half of the Gate-1 ship floor: "
            f"top-2 stability {stability:.4f} < {em.GATE1_MIN_TOP2_STABILITY}. ADR 0005 "
            "gives this half no mitigation - an unstable model gives different "
            "recommendations to the same user depending on which resample trained it, "
            "and the ranking is the product. This escalates as a project-level finding "
            "rather than shipping."
        )
    print(f"Gate 1: top-2 stability {stability:.4f} vs >= {em.GATE1_MIN_TOP2_STABILITY} "
          f"({'CLEARS' if decision['stability_clears'] else 'FAILS'}, hard half); "
          f"ECE {ece:.4f} vs <= {em.GATE1_MAX_ECE} "
          f"({'clears' if decision['ece_clears'] else 'FAILS'}, mitigable half) "
          f"-> deployment status {decision['status']!r}")

    # Deployment temperature: one constant from all available held-out predictions of
    # the exact configuration being serialized. `oof` is SeedEnsemble.predict_proba —
    # the mean of the members' PROBABILITIES — which is the quantity matcher_nn takes
    # the logit of. See the module docstring.
    temperature = fit_temperature(oof, y)
    print(f"deployment temperature {temperature:.2f} (fitted on ensemble-averaged OOF)")

    fitted = factory().fit(X, y)
    members, scaler_mean, scaler_scale = serialize_members(fitted, X)
    n_constant = int(constant_feature_mask(X).sum())
    if n_constant:
        print(f"{n_constant} feature(s) were constant in training; their fixed "
              "contribution is folded into the first layer's bias and their scale "
              "exported as 0.0 (see fold_constant_features)")

    artifact = {
        "model_version": MODEL_VERSION,
        "model_type": MODEL_TYPE,
        "feature_version": FEATURE_VERSION,
        "feature_names": feature_names,
        "careers": careers,
        "scaler_mean": scaler_mean,
        "scaler_scale": scaler_scale,
        "activation": "relu",
        "members": members,
        "temperature": temperature,
        "label_source": "synthetic_llm (bank-consistent silver labels; see caveats)",
        "caveats": build_caveats(df, careers, decision),
        "deployment": {
            # A string, not a boolean — see gate1_decision.
            "status": decision["status"],
            "ranking": "this model",
            "match_percent": (
                "this model" if decision["ece_clears"]
                else "FALL BACK TO THE FORMULA - this model's percentages are uncalibrated"
            ),
            "mitigation_applied": (
                None if decision["ece_clears"]
                else "ADR 0005 mitigable-ECE branch: ships as the ranking source only"
            ),
        },
        "selection": {
            "selected_variant": round2["selected_variant"],
            "selected_by": "sweep_round2.py (DEV-95), nested 14-Variant sweep",
            "specification": spec,
            # Recomputed for the exact exported configuration, not inherited.
            "exported_config_gate1": {
                **{k: decision[k] for k in (
                    "ece", "ece_floor", "ece_clears",
                    "top2_stability", "stability_floor", "stability_clears")},
                "protocol": (
                    "evaluate_matchers.cv_oof_and_stability + rank_metrics at "
                    f"random_state={spec['random_state']}, after assert_deterministic"
                ),
                "reproduces_recorded_ship_floor": True,
                "recorded_ship_floor_drift": drift,
            },
            "ship_floor_across_seeds": round2.get("ship_floor_across_seeds"),
        },
        "training": {
            "n_rows": len(df),
            "dataset_digest": current_digest,
            "rows_by_label": {k: int(v) for k, v in
                              df["label_top1"].value_counts().to_dict().items()},
            "n_members": spec["n_members"],
            "member_seeds": [spec["random_state"] + i for i in range(spec["n_members"])],
            "hidden_sizes": spec["member"]["hidden_sizes"],
            "seed": spec["random_state"],
            "unrecorded_hyperparameters": unrecorded,
            # Folded into the first layer's bias and exported with scale 0.0,
            # because NNClassifier's ~1e-8 scale on these columns does not survive
            # the float32 -> float64 change of runtime. See fold_constant_features.
            "constant_features": [n for n, c in
                                  zip(feature_names, constant_feature_mask(X)) if c],
            "chroma_snapshot": meta["chroma_snapshot"],
            "silver_prompt_versions": meta["silver_prompt_versions"],
            "trained_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
