"""Export the Gate 2 winner as a serving artifact (matching rework Phase 4/5).

Selects logistic C by stratified 5-fold CV on the full silver dataset, trains the
final class-balanced pipeline on ALL rows, and writes a dependency-free JSON
artifact (scaler stats + coefficients) that backend/app/services/matcher_model.py
loads. No pickle, no sklearn needed at serve time.

Output: data/models/matcher_logistic_v1.json
Run from repo root: python data/scripts/export_model.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[2]
# The matching internals moved to services/ at the DEV-43 cutover:
# services/ provides the `common` package, services/matching the `app` package.
sys.path.insert(0, str(REPO_ROOT / "services"))
sys.path.insert(0, str(REPO_ROOT / "services" / "matching"))

from dataset_guards import dataset_caveats, dataset_digest  # noqa: E402

from app.services.feature_builder import FEATURE_VERSION  # noqa: E402

TRAINING_DIR = REPO_ROOT / "data" / "training"
OUT_PATH = REPO_ROOT / "data" / "models" / "matcher_logistic_v2.json"

SEED = 42
C_GRID = [0.05, 0.25, 1.0, 4.0]
MODEL_VERSION = "matcher-logistic-v2"


def build_caveats(df: pd.DataFrame, careers: list[str]) -> list[str]:
    """Caveats travel INSIDE the artifact so every consumer of the model's results
    sees them. The circularity caveat is a property of the labeling protocol; the
    class-balance ones come from dataset_guards.dataset_caveats (shared with the
    Phase-2 report) so a rerun on refreshed data embeds its own counts."""
    return [
        "Labels are bank-consistent, not independently validated: silver labels come "
        "from an LLM panel whose stage-2 vote follows the answer key derived from "
        "careers.json bonuses ~94% of the time it speaks. Panel-agreement metrics "
        "measure fidelity to the hand-authored bonus table, not real-world accuracy.",
        *dataset_caveats(df["label_top1"], careers),
    ]


def main() -> None:
    df = pd.read_parquet(TRAINING_DIR / "train_features.parquet")
    meta = json.loads((TRAINING_DIR / "dataset_metadata.json").read_text(encoding="utf-8"))
    feature_names = meta["feature_names"]
    careers = [n[: -len("_fit")] for n in feature_names if n.endswith("_fit")]
    if meta["feature_version"] != FEATURE_VERSION:
        raise SystemExit("dataset feature_version != code FEATURE_VERSION — rebuild the dataset")

    # This exporter produces logistic-regression artifacts only (the serving path
    # is linear). Require Phase 3's explicit deployment selection to agree, so the
    # published artifact can never silently diverge from the selection report.
    gate2_path = TRAINING_DIR / "gate2_winner.json"
    if not gate2_path.exists():
        raise SystemExit(f"{gate2_path} not found — run train_models.py (Phase 3) first.")
    gate2 = json.loads(gate2_path.read_text(encoding="utf-8"))
    if gate2.get("deployable") is None:
        raise SystemExit(
            "gate2_winner.json records no deployable model — no servable architecture "
            f"qualified under Gate 1 ({gate2.get('gate1')}); nothing may be exported. "
            f"Reason recorded: {gate2.get('deployable_reason')!r}"
        )
    if gate2.get("deployable") != "logistic_tuned":
        raise SystemExit(
            f"gate2_winner.json deployable={gate2.get('deployable')!r} but this exporter "
            "produces logistic only — reconcile the deployment selection (train_models.py) "
            "or build a serving path for that architecture before exporting."
        )
    # The selection must have been computed on THIS dataset content — the digest
    # hashes the loaded features+labels, so a regenerated OR hand-edited
    # train_features.parquet (even with an unchanged row count and stale sidecar
    # metadata) cannot be paired with an obsolete selection.
    current_digest = dataset_digest(df, feature_names)
    if gate2.get("dataset_digest") != current_digest:
        raise SystemExit(
            "gate2_winner.json was produced for different dataset content "
            f"(digest {gate2.get('dataset_digest')!r} vs current {current_digest!r}) — "
            "rerun evaluate_matchers.py and train_models.py on the current "
            "train_features.parquet first."
        )

    # Require Phase 3's calibration record so export cannot proceed from a verdict
    # that predates DEV-91. Its deployment temperature belongs to nested-CV
    # `logistic_tuned`, however, and is provenance only: export selects one fixed C
    # below and must fit a fresh temperature for that exact configuration.
    calibration = gate2.get("calibration") or {}
    if calibration.get("deployment_temperature") is None:
        raise SystemExit(
            "gate2_winner.json records no calibration.deployment_temperature — it "
            "predates the cross-fitted-temperature re-baseline (DEV-91, ADR 0007). "
            "Rerun train_models.py before exporting."
        )
    if calibration.get("deployment_temperature_model") != gate2["deployable"]:
        raise SystemExit(
            "gate2_winner.json's deployment temperature was fitted for "
            f"{calibration.get('deployment_temperature_model')!r} but the deployable "
            f"model is {gate2['deployable']!r} — a temperature does not transfer "
            "between models; rerun train_models.py."
        )

    X = df[feature_names].to_numpy(dtype=float)
    y = df["label_top1"].map({c: i for i, c in enumerate(careers)}).to_numpy()

    def cv_top2(C: float) -> float:
        hits = []
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y):
            m = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=C, max_iter=5000, class_weight="balanced", random_state=SEED),
            ).fit(X[tr], y[tr])
            top2 = np.argsort(-m.predict_proba(X[te]), axis=1)[:, :2]
            hits += [y[te][i] in top2[i] for i in range(len(te))]
        return float(np.mean(hits))

    scores = {C: cv_top2(C) for C in C_GRID}
    best_c = max(scores, key=scores.get)
    print("C grid top-2:", scores, "-> chosen C =", best_c)

    # Gate-1 qualification was measured on the Phase-2 default configuration and
    # does NOT transfer across hyperparameters: calibration and stability depend
    # on C. Revalidate the EXACT configuration being exported, same protocol and
    # thresholds, and refuse to ship one the gate would reject.
    from evaluate_matchers import (  # noqa: E402  (sibling script, sys.path[0])
        GATE1_MAX_ECE, GATE1_MIN_TOP2_STABILITY, cv_oof_and_stability, rank_metrics,
    )
    from train_models import fit_temperature  # noqa: E402

    def exported_config():
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(C=best_c, max_iter=5000, class_weight="balanced", random_state=SEED),
        )

    oof, config_stability = cv_oof_and_stability(X, y, exported_config, len(careers))
    config_ece = rank_metrics(oof, y, oof, len(careers))["ece"]
    # Deployment wants one constant estimated from all available held-out
    # predictions. These OOF probabilities come from the exact fixed-C estimator
    # serialized below; the Phase-3 temperature cannot be transferred because its
    # OOF folds independently selected heterogeneous Cs.
    deployment_temperature = fit_temperature(oof, y)
    if config_ece > GATE1_MAX_ECE or config_stability < GATE1_MIN_TOP2_STABILITY:
        raise SystemExit(
            f"exported configuration C={best_c} violates the Gate-1 thresholds "
            f"(ECE {config_ece:.3f} vs <= {GATE1_MAX_ECE}, top-2 stability "
            f"{config_stability:.3f} vs >= {GATE1_MIN_TOP2_STABILITY}) — Gate-1 "
            "qualification does not transfer between configurations; adjust the C "
            "grid or revisit the gate before exporting."
        )
    print(f"exported config C={best_c}: ECE {config_ece:.3f}, "
          f"top-2 stability {config_stability:.3f}, "
          f"deployment T {deployment_temperature:.2f} "
          "— Gate-1 thresholds satisfied")

    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_c, max_iter=5000, class_weight="balanced", random_state=SEED),
    ).fit(X, y)
    scaler: StandardScaler = pipe.named_steps["standardscaler"]
    clf: LogisticRegression = pipe.named_steps["logisticregression"]

    artifact = {
        "model_version": MODEL_VERSION,
        "model_type": "multinomial_logistic_regression",
        "feature_version": FEATURE_VERSION,
        "feature_names": feature_names,
        "careers": careers,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coef": clf.coef_.tolist(),
        "intercept": clf.intercept_.tolist(),
        # Fitted on pooled OOF from the exact fixed-C configuration serialized in
        # this artifact, rather than transferred from Phase 3's heterogeneous
        # per-fold logistic configurations.
        "temperature": deployment_temperature,
        "label_source": "synthetic_llm (bank-consistent silver labels; see caveats)",
        "caveats": build_caveats(df, careers),
        "selection": {
            "gate2_winner": gate2["winner"],
            "deployable": gate2["deployable"],
            "reason": gate2["deployable_reason"],
            "gate1": gate2.get("gate1"),
            # Gate-1 metrics recomputed for the exact exported configuration —
            # not inherited from the Phase-2 default config.
            "exported_config_gate1": {
                "C": best_c,
                "ece": round(config_ece, 4),
                "top2_stability": round(config_stability, 4),
                "thresholds": {"max_ece": GATE1_MAX_ECE,
                               "min_top2_stability": GATE1_MIN_TOP2_STABILITY},
            },
        },
        "training": {
            "n_rows": len(df),
            "dataset_digest": current_digest,
            "rows_by_label": {k: int(v) for k, v in df["label_top1"].value_counts().to_dict().items()},
            "C": best_c,
            "cv_top2_by_C": scores,
            "class_weight": "balanced",
            "seed": SEED,
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
