"""Phase 2 of the matching-module rework: baselines + Gate 1.

Evaluates four scorers on the silver-label feature table under stratified 5-fold CV:

    formula        the current production blend (0.40 fit + 0.40 semantic + 0.20 skill)
    logistic       multinomial logistic regression, class-balanced, standardized
    lightgbm       gradient-boosted trees, class-balanced
    archetype_nn   zero-train cosine to the LLM-panel career archetypes

FRAMING: every metric here is **agreement with the synthetic LLM panel** (silver
labels), not expert-validated accuracy. A scorer that wins has learned to predict
the panel — nothing more.

Gate 1: a learned model must beat the formula on top-2 agreement by a meaningful
margin, or the rework stops at the formula.

Output: data/training/baseline_evaluation.md
Run from repo root: python data/scripts/evaluate_matchers.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAINING_DIR = REPO_ROOT / "data" / "training"
FEATURES_PARQUET = TRAINING_DIR / "train_features.parquet"
METADATA_JSON = TRAINING_DIR / "dataset_metadata.json"
ARCHETYPES_PARQUET = TRAINING_DIR / "archetypes_synthetic.parquet"
OUT_MD = TRAINING_DIR / "baseline_evaluation.md"

SEED = 42
N_FOLDS = 5
QUESTION_IDS = [f"q{i}" for i in range(1, 11)]

# Same weights as backend/app/services/matching_service.FORMULA_WEIGHTS.
FORMULA_WEIGHTS = {"fit": 0.40, "sem": 0.40, "skill": 0.20}


def load_data():
    df = pd.read_parquet(FEATURES_PARQUET)
    meta = json.loads(METADATA_JSON.read_text(encoding="utf-8"))
    feature_names = meta["feature_names"]
    careers = [n[: -len("_fit")] for n in feature_names if n.endswith("_fit")]
    return df, feature_names, careers, meta


def formula_scores(df: pd.DataFrame, careers: list[str]) -> np.ndarray:
    """Current production blend per career, from the feature columns themselves."""
    cols = []
    for cid in careers:
        s = (
            FORMULA_WEIGHTS["fit"] * df[f"{cid}_fit"]
            + FORMULA_WEIGHTS["sem"] * df[f"{cid}_sem"]
            + FORMULA_WEIGHTS["skill"] * df[f"{cid}_skill"]
        )
        cols.append(s.to_numpy())
    return np.column_stack(cols)


def archetype_scores(df: pd.DataFrame, careers: list[str]) -> np.ndarray:
    """Cosine similarity between the profile's answered ordinals and each career's
    mean panel archetype, computed only over answered questions."""
    arch = pd.read_parquet(ARCHETYPES_PARQUET)
    arch_vecs = {cid: arch[arch.career_id == cid][QUESTION_IDS].mean().to_numpy() for cid in careers}

    answers = df[QUESTION_IDS].to_numpy(dtype=float)
    present = df[[f"{q}_present" for q in QUESTION_IDS]].to_numpy(dtype=bool)

    scores = np.zeros((len(df), len(careers)))
    for i in range(len(df)):
        mask = present[i]
        if not mask.any():
            continue
        a = answers[i][mask]
        for j, cid in enumerate(careers):
            b = arch_vecs[cid][mask]
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            scores[i, j] = float(a @ b / denom) if denom > 0 else 0.0
    return scores


def softmax(x: np.ndarray) -> np.ndarray:
    z = x - x.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def rank_metrics(scores: np.ndarray, y_idx: np.ndarray, probs: np.ndarray, n_classes: int) -> dict:
    order = np.argsort(-scores, axis=1)  # descending
    ranks = np.array([int(np.where(order[i] == y_idx[i])[0][0]) for i in range(len(y_idx))])
    top1 = float((ranks == 0).mean())
    top2 = float((ranks <= 1).mean())
    top3 = float((ranks <= 2).mean())
    mrr = float((1.0 / (ranks + 1)).mean())

    # Per-class top-1 recall (dead-class detector under imbalance).
    per_class = {}
    pred = order[:, 0]
    for c in range(n_classes):
        m = y_idx == c
        per_class[c] = float((pred[m] == c).mean()) if m.any() else float("nan")
    balanced = float(np.nanmean(list(per_class.values())))

    # ECE (10 bins) on the top-1 probability.
    conf = probs[np.arange(len(probs)), pred]
    correct = (pred == y_idx).astype(float)
    ece, bins = 0.0, np.linspace(0.0, 1.0, 11)
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf >= lo) & (conf < hi) if hi < 1.0 else (conf >= lo) & (conf <= hi)
        if m.any():
            ece += (m.mean()) * abs(conf[m].mean() - correct[m].mean())

    return {"top1": top1, "top2": top2, "top3": top3, "mrr": mrr,
            "balanced_top1": balanced, "ece": float(ece), "per_class": per_class}


def make_logistic():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=5000, class_weight="balanced", random_state=SEED),
    )


def make_lightgbm():
    return LGBMClassifier(
        n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=5,
        subsample=0.9, colsample_bytree=0.8, class_weight="balanced",
        random_state=SEED, verbose=-1,
    )


def main() -> None:
    df, feature_names, careers, meta = load_data()
    X = df[feature_names].to_numpy(dtype=float)
    label_to_idx = {c: i for i, c in enumerate(careers)}
    y = df["label_top1"].map(label_to_idx).to_numpy()
    n_classes = len(careers)

    # Precomputed (train-free) scorer score matrices over ALL rows.
    static_scores = {
        "formula": formula_scores(df, careers),
        "archetype_nn": archetype_scores(df, careers),
    }

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    # Out-of-fold predictions pooled across folds, one array per scorer.
    oof_scores = {name: np.zeros((len(df), n_classes)) for name in
                  ["formula", "archetype_nn", "logistic", "lightgbm"]}

    for tr_idx, te_idx in skf.split(X, y):
        for name, s in static_scores.items():
            oof_scores[name][te_idx] = s[te_idx]

        logit = make_logistic().fit(X[tr_idx], y[tr_idx])
        oof_scores["logistic"][te_idx] = logit.predict_proba(X[te_idx])

        gbm = make_lightgbm().fit(X[tr_idx], y[tr_idx])
        oof_scores["lightgbm"][te_idx] = gbm.predict_proba(X[te_idx])

    results = {}
    for name, s in oof_scores.items():
        # Trained models already emit probabilities; static scorers get a softmax
        # so ECE is computable (flagged as pseudo-probabilities in the report).
        probs = s if name in ("logistic", "lightgbm") else softmax(s * 10.0)
        results[name] = rank_metrics(s, y, probs, n_classes)

    # ---- report
    def fmt_row(name, m):
        return (f"| {name} | {m['top1']:.3f} | {m['top2']:.3f} | {m['top3']:.3f} | "
                f"{m['mrr']:.3f} | {m['balanced_top1']:.3f} | {m['ece']:.3f} |")

    per_class_tables = []
    for name, m in results.items():
        rows = "\n".join(f"| {careers[c]} | {v:.2f} |" for c, v in m["per_class"].items())
        per_class_tables.append(f"### {name}\n\n| career | top-1 recall |\n|---|---|\n{rows}")

    formula_top2 = results["formula"]["top2"]
    best_learned = max(("logistic", "lightgbm"), key=lambda n: results[n]["top2"])
    margin = results[best_learned]["top2"] - formula_top2
    gate1 = margin >= 0.05  # meaningful-margin threshold, stated in the report

    report = f"""# Baseline Evaluation — Phase 2 / Gate 1

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** A high number means the scorer predicts the panel's
> labels; it does not certify real-world recommendation quality.

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Dataset: {len(df)} rows ({meta["rows_by_source"]}), feature version `{meta["feature_version"]}`,
Chroma snapshot {meta["chroma_snapshot"]["document_count"]} docs.
Protocol: stratified {N_FOLDS}-fold CV (seed {SEED}); metrics on pooled out-of-fold
predictions. Trained scorers use class weights (labels are imbalanced: PM=14, FE=17).

## Comparison

| scorer | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE* |
|---|---|---|---|---|---|---|
{fmt_row("formula (production)", results["formula"])}
{fmt_row("archetype_nn (zero-train)", results["archetype_nn"])}
{fmt_row("logistic (balanced)", results["logistic"])}
{fmt_row("lightgbm (balanced)", results["lightgbm"])}

*ECE for `formula` and `archetype_nn` is computed on softmax-normalized scores
(pseudo-probabilities) — directional only. Trained models emit real probabilities.

## Per-class top-1 recall

{chr(10).join(per_class_tables)}

## Gate 1 verdict

- Formula top-2 agreement: **{formula_top2:.3f}**
- Best learned model: **{best_learned}** at top-2 **{results[best_learned]["top2"]:.3f}**
  (margin {margin:+.3f}; threshold for "meaningful" set at +0.05)
- **Gate 1: {"PASSED — proceed to Phase 3" if gate1 else "NOT PASSED — the learned models do not beat the formula meaningfully; stop or revisit labels"}**

Caveats:
- Circularity: the formula's inputs (fit/sem/skill) are also model features, and
  formula-vs-panel top-1 agreement was 43.4% at labeling time — partial circularity
  in both directions; see synthetic_agreement_report.md.
- {len(df[df.profile_source == "real"])} real profiles ride along in the pool; far too few
  for a separate evaluation slice.
"""
    OUT_MD.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
