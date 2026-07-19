"""Phase 2 of the matching-module rework: baselines + Gate 1.

Evaluates four scorers on the silver-label feature table under stratified 5-fold CV:

    formula        the current production blend (0.40 fit + 0.40 semantic + 0.20 skill)
    logistic       multinomial logistic regression, class-balanced, standardized
    lightgbm       gradient-boosted trees, class-balanced
    archetype_nn   zero-train cosine to the LLM-panel career archetypes

FRAMING: panel-agreement metrics are **agreement with the synthetic LLM panel**
(silver labels), not expert-validated accuracy — and under panel-v2.x the labels
are confirmed circular with the hand-authored career weights (stage-2 votes follow
the bonus-derived answer key ~94% of the time it speaks). A scorer that wins on
agreement has learned the bonus table — nothing more. Agreement is therefore
reported descriptively only.

Gate 1 (reframed 2026-07-18): a learned model must be (a) well-calibrated against
the silver labels — pooled out-of-fold ECE <= GATE1_MAX_ECE — and (b) stable in
what it recommends: mean pairwise Jaccard of the top-2 sets produced by the five
fold-models over all rows >= GATE1_MIN_TOP2_STABILITY. Beating the formula on
panel agreement is NOT a criterion.

Output: data/training/baseline_evaluation.md
Run from repo root: python data/scripts/evaluate_matchers.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dataset_guards import assert_min_class_coverage, dataset_caveats, dataset_digest

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAINING_DIR = REPO_ROOT / "data" / "training"
FEATURES_PARQUET = TRAINING_DIR / "train_features.parquet"
METADATA_JSON = TRAINING_DIR / "dataset_metadata.json"
ARCHETYPES_PARQUET = TRAINING_DIR / "archetypes_synthetic.parquet"
OUT_MD = TRAINING_DIR / "baseline_evaluation.md"
OUT_GATE1 = TRAINING_DIR / "gate1_verdict.json"

SEED = 42
N_FOLDS = 5
# Raw-answer feature columns (q1, q2, …) are derived from the data, never hardcoded,
# so new questions in the bank flow through without a change here.
_QID_RE = re.compile(r"q\d+$")

# Same weights as backend/app/services/matching_service.FORMULA_WEIGHTS.
FORMULA_WEIGHTS = {"fit": 0.40, "sem": 0.40, "skill": 0.20}

# Gate-1 thresholds (judgment calls, stated in the report): calibration and
# recommendation stability, replacing the circular beats-the-formula criterion.
GATE1_MAX_ECE = 0.10
GATE1_MIN_TOP2_STABILITY = 0.60


def load_data():
    df = pd.read_parquet(FEATURES_PARQUET)
    meta = json.loads(METADATA_JSON.read_text(encoding="utf-8"))
    feature_names = meta["feature_names"]
    careers = [n[: -len("_fit")] for n in feature_names if n.endswith("_fit")]
    # Guard even though Phase 1 also checks: this script may be pointed at an
    # older/hand-built parquet, and stratified 5-fold CV silently degrades below
    # 5 labels per class.
    assert_min_class_coverage(df["label_top1"], careers, context="train_features.parquet")
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
    question_ids = [c for c in df.columns if _QID_RE.fullmatch(c)]
    arch_vecs = {cid: arch[arch.career_id == cid][question_ids].mean().to_numpy() for cid in careers}

    answers = df[question_ids].to_numpy(dtype=float)
    present = df[[f"{q}_present" for q in question_ids]].to_numpy(dtype=bool)

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
    # Stability sub-model top-2 sets, collected per outer fold on that fold's TEST
    # rows only: sub-models are trained on inner resamples of the outer training
    # partition, so the rows they're compared on are unseen by every sub-model —
    # predicting over all rows would let shared training rows inflate agreement.
    INNER_SPLITS = 3  # floor class has ~4 members inside an outer training partition
    stability_pairs = {"logistic": [], "lightgbm": []}

    for tr_idx, te_idx in skf.split(X, y):
        for name, s in static_scores.items():
            oof_scores[name][te_idx] = s[te_idx]

        logit = make_logistic().fit(X[tr_idx], y[tr_idx])
        oof_scores["logistic"][te_idx] = logit.predict_proba(X[te_idx])

        gbm = make_lightgbm().fit(X[tr_idx], y[tr_idx])
        oof_scores["lightgbm"][te_idx] = gbm.predict_proba(X[te_idx])

        inner = StratifiedKFold(n_splits=INNER_SPLITS, shuffle=True, random_state=SEED)
        sub_top2 = {"logistic": [], "lightgbm": []}
        for sub_tr, _ in inner.split(X[tr_idx], y[tr_idx]):
            idx = tr_idx[sub_tr]
            sub_logit = make_logistic().fit(X[idx], y[idx])
            sub_top2["logistic"].append(np.argsort(-sub_logit.predict_proba(X[te_idx]), axis=1)[:, :2])
            sub_gbm = make_lightgbm().fit(X[idx], y[idx])
            sub_top2["lightgbm"].append(np.argsort(-sub_gbm.predict_proba(X[te_idx]), axis=1)[:, :2])
        for name, preds in sub_top2.items():
            for i in range(len(preds)):
                for j in range(i + 1, len(preds)):
                    a, b = preds[i], preds[j]
                    inter = np.array([len(set(a[r]) & set(b[r])) for r in range(len(a))], dtype=float)
                    union = np.array([len(set(a[r]) | set(b[r])) for r in range(len(a))], dtype=float)
                    stability_pairs[name].append(float((inter / union).mean()))

    # Mean pairwise Jaccard of top-2 sets across inner sub-models, evaluated only on
    # rows unseen by all of them, averaged over outer folds.
    stability = {name: float(np.mean(vals)) for name, vals in stability_pairs.items()}

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

    # Class balance: label share vs each scorer's predicted share (over-prediction check).
    label_share = {c: float((y == i).mean()) for i, c in enumerate(careers)}
    pred_share = {
        name: {careers[c]: float((np.argsort(-s, axis=1)[:, 0] == c).mean()) for c in range(n_classes)}
        for name, s in oof_scores.items()
    }
    # Silver labels are only used for the heuristic-agreement caveat — but they
    # must describe the SAME population the metrics were computed on. If Phase 0
    # regenerated silver_labels.parquet without a Phase-1 rebuild, refuse rather
    # than report provenance for rows that were never evaluated.
    silver = pd.read_parquet(TRAINING_DIR / "silver_labels.parquet")
    aligned = df[["profile_id", "label_top1"]].merge(
        silver[["profile_id", "label_top1", "heuristic_fit_top1"]],
        on="profile_id", how="left", suffixes=("", "_silver"),
    )
    if aligned["label_top1_silver"].isna().any() or \
            (aligned["label_top1"] != aligned["label_top1_silver"]).any():
        raise SystemExit(
            "train_features.parquet does not match silver_labels.parquet (profile "
            "ids or labels diverge) — Phase 0 was regenerated without rebuilding "
            "Phase 1; run build_training_set.py first."
        )
    # heuristic_fit_top1 is the questionnaire-only answer-key winner (no semantic/
    # skill signals) — distinct from the production formula, whose agreement is
    # results["formula"]["top1"]. Label both precisely; conflating them overstated
    # "formula agreement" in earlier reports.
    heuristic_agree = float((aligned["label_top1"] == aligned["heuristic_fit_top1"]).mean())
    # Prompt versions come from the evaluated table itself, not the silver file.
    prompt_versions = sorted(df["prompt_version"].unique().tolist())

    # Gate 1 (reframed): calibration + top-2 recommendation stability. The gate is
    # existential — it passes if ANY learned model clears both thresholds; the
    # preferred candidate is the best-calibrated of the qualifiers (falling back to
    # best-calibrated overall for reporting when none qualify).
    learned = ("logistic", "lightgbm")
    qualifiers = [n for n in learned
                  if results[n]["ece"] <= GATE1_MAX_ECE and stability[n] >= GATE1_MIN_TOP2_STABILITY]
    gate1 = bool(qualifiers)
    best_learned = min(qualifiers or learned, key=lambda n: results[n]["ece"])
    best_ece = results[best_learned]["ece"]
    best_stab = stability[best_learned]
    gate_rows = "\n".join(
        f"| {n} | {results[n]['ece']:.3f} | {'yes' if results[n]['ece'] <= GATE1_MAX_ECE else 'NO'} | "
        f"{stability[n]:.3f} | {'yes' if stability[n] >= GATE1_MIN_TOP2_STABILITY else 'NO'} | "
        f"{'QUALIFIES' if n in qualifiers else '—'} |"
        for n in learned
    )

    balance_rows = "\n".join(
        f"| {c} | {label_share[c]:.1%} | {pred_share['formula'][c]:.1%} | "
        f"{pred_share['logistic'][c]:.1%} | {pred_share['lightgbm'][c]:.1%} |"
        for c in careers
    )

    report = f"""# Baseline Evaluation — Phase 2 / Gate 1 (reframed)

> **CAVEATS THAT TRAVEL WITH EVERY RESULT BELOW**
> - Silver labels are **bank-consistent, not independently validated**: the
> panel's stage-2 vote follows the answer key derived from careers.json bonuses
> ~94% of the time it speaks. In this dataset the labels agree with the
> questionnaire-only heuristic fit (the answer-key winner) **{heuristic_agree:.1%}**
> of the time, and with the full production formula (fit+sem+skill) top-1
> **{results["formula"]["top1"]:.1%}** of the time. Panel-agreement numbers measure
> fidelity to the hand-authored bonus table, nothing more — Gate 1 no longer uses them.
{chr(10).join(f"> - {c}" for c in dataset_caveats(df["label_top1"], careers)) or "> - (no class-balance caveats: no floor-level or over-represented classes in this dataset)"}

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Dataset: {len(df)} rows ({meta["rows_by_source"]}), feature version `{meta["feature_version"]}`,
labels `{", ".join(prompt_versions)}`, Chroma snapshot {meta["chroma_snapshot"]["document_count"]} docs.
Protocol: stratified {N_FOLDS}-fold CV (seed {SEED}); metrics on pooled out-of-fold
predictions. Both trained scorers use class_weight="balanced".

## Comparison (panel agreement is DESCRIPTIVE only — see caveat a)

| scorer | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE* | top-2 stability |
|---|---|---|---|---|---|---|---|
{fmt_row("formula (production)", results["formula"])} 1.000** |
{fmt_row("archetype_nn (zero-train)", results["archetype_nn"])} 1.000** |
{fmt_row("logistic (balanced)", results["logistic"])} {stability["logistic"]:.3f} |
{fmt_row("lightgbm (balanced)", results["lightgbm"])} {stability["lightgbm"]:.3f} |

*ECE for `formula` and `archetype_nn` is computed on softmax-normalized scores
(pseudo-probabilities) — directional only. Trained models emit real probabilities.
**Static scorers involve no training, so resampling stability is 1.0 by construction.

## Class balance: label share vs predicted share (over-prediction check)

| career | label share | formula pred | logistic pred | lightgbm pred |
|---|---|---|---|---|
{balance_rows}

## Per-class top-1 recall

{chr(10).join(per_class_tables)}

## Gate 1 verdict (reframed: calibration + stability, NOT beats-the-formula)

The gate is existential: it passes if any learned model clears BOTH thresholds
(ECE <= {GATE1_MAX_ECE}, stability >= {GATE1_MIN_TOP2_STABILITY}).

| model | ECE | calibrated? | top-2 stability | stable? | verdict |
|---|---|---|---|---|---|
{gate_rows}

- Preferred candidate (best-calibrated qualifier): **{best_learned}**
  (ECE {best_ece:.3f}, stability {best_stab:.3f})
- **Gate 1: {"PASSED — proceed to Phase 3" if gate1 else "NOT PASSED — no learned model clears both thresholds; stop or revisit labels"}**

The old criterion ("beat the formula on panel agreement") is reported above for
transparency but is not meaningful under key-anchored labeling — a model wins it by
learning the bonus table (see caveat a).

Additional notes:
- {len(df[df.profile_source == "real"])} real profiles ride along in the pool; far too few
  for a separate evaluation slice.
"""
    OUT_MD.write_text(report, encoding="utf-8")
    print(report)

    # Machine-readable Gate-1 verdict: Phase 3 consults this to decide whether a
    # servable model is actually deployable, and export refuses without it — the
    # markdown report alone cannot gate anything downstream.
    digest = dataset_digest(df, feature_names)
    OUT_GATE1.write_text(json.dumps({
        "passed": gate1,
        "qualifiers": qualifiers,
        "preferred": best_learned if gate1 else None,
        "thresholds": {"max_ece": GATE1_MAX_ECE, "min_top2_stability": GATE1_MIN_TOP2_STABILITY},
        "metrics": {n: {"ece": results[n]["ece"], "top2_stability": stability[n]} for n in learned},
        "dataset_digest": digest,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_GATE1} (passed={gate1}, qualifiers={qualifiers})")


if __name__ == "__main__":
    main()
