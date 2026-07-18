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
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dataset_guards import MIN_LABELS_PER_CAREER  # noqa: E402

from app.services.feature_builder import FEATURE_VERSION  # noqa: E402

TRAINING_DIR = REPO_ROOT / "data" / "training"
OUT_PATH = REPO_ROOT / "data" / "models" / "matcher_logistic_v2.json"

SEED = 42
C_GRID = [0.05, 0.25, 1.0, 4.0]
MODEL_VERSION = "matcher-logistic-v2"


def build_caveats(df: pd.DataFrame) -> list[str]:
    """Caveats travel INSIDE the artifact so every consumer of the model's results
    sees them. The class-balance ones are derived from the loaded dataset so a
    rerun on refreshed data reports its own counts, not a previous run's."""
    counts = df["label_top1"].value_counts()
    n = len(df)
    floor = [f"{c} ({int(v)} labels)" for c, v in counts.items() if v <= MIN_LABELS_PER_CAREER]
    over = [f"{c} ({int(v)}/{n} rows, {v / n:.0%})" for c, v in counts.items()
            if v / n > 2.0 / len(counts)]
    caveats = [
        "Labels are bank-consistent, not independently validated: silver labels come "
        "from an LLM panel whose stage-2 vote follows the answer key derived from "
        "careers.json bonuses ~94% of the time it speaks. Panel-agreement metrics "
        "measure fidelity to the hand-authored bonus table, not real-world accuracy.",
    ]
    if floor:
        caveats.append(
            f"Floor-level class representation for {', '.join(sorted(floor))} — at or "
            f"below the {MIN_LABELS_PER_CAREER}-label stratified-CV minimum; treat "
            "their predictions and metrics as low-confidence."
        )
    if over:
        caveats.append(
            f"Over-represented classes: {', '.join(sorted(over))} (more than 2x the "
            "uniform share). class_weight='balanced' prevents amplification during "
            "training, but the label skew remains in the data."
        )
    return caveats


def main() -> None:
    df = pd.read_parquet(TRAINING_DIR / "train_features.parquet")
    meta = json.loads((TRAINING_DIR / "dataset_metadata.json").read_text(encoding="utf-8"))
    feature_names = meta["feature_names"]
    careers = [n[: -len("_fit")] for n in feature_names if n.endswith("_fit")]
    if meta["feature_version"] != FEATURE_VERSION:
        raise SystemExit("dataset feature_version != code FEATURE_VERSION — rebuild the dataset")

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
        "temperature": 1.0,  # Gate 2: raw probabilities were best-calibrated
        "label_source": "synthetic_llm (bank-consistent silver labels; see caveats)",
        "caveats": build_caveats(df),
        "training": {
            "n_rows": len(df),
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
