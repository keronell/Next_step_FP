"""Phase 2 of the matching-module rework: baselines + Gate 1.

Evaluates five scorers on the silver-label feature table under stratified 5-fold CV:

    formula        the current production blend (0.40 fit + 0.40 semantic + 0.20 skill)
    logistic       multinomial logistic regression, class-balanced, standardized
    lightgbm       gradient-boosted trees, class-balanced
    small_nn       deterministic MLP (nn_model.NNClassifier), class-balanced
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

The neural matcher joins the gate (2026-07-27, plan Step 3.1). Until then its
rejection was an assertion in a Phase-3 report rather than a gate verdict — the
candidate list was hardcoded to logistic and lightgbm. It is scored through the
same cv_oof_and_stability(), the same folds and the same thresholds, with no
special-casing, and it is fed HARD labels like every other candidate. The
soft-target variant, which trains on the panel's vote distribution, is a genuinely
different objective and stays a Gate-2 challenger in train_models.py; the
asymmetry is handled by the pattern already in the repo, where export revalidates
the exact shipped configuration against these thresholds.

Run from repo root, in the hash-pinned training venv (see data/scripts/README.md):

    data/venv-training/bin/python data/scripts/evaluate_matchers.py

Outputs: data/training/baseline_evaluation.md, data/training/gate1_verdict.json
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
from env_manifest import environment_manifest, manifest_markdown
from nn_model import NNClassifier

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

# The Gate-1 candidate list. Trained scorers only — the static scorers below are
# training-free and are reported for reference, never gated.
LEARNED = ("logistic", "lightgbm", "small_nn")

# Seeds for the REPORTED-ONLY reseeded-stability number (see reseeded_stability).
# Three of them, matching INNER_SPLITS, so the two stability numbers are each a
# mean over three pairwise comparisons per fold and are read at the same precision.
RESEED_SEEDS = (SEED, SEED + 1, SEED + 2)


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


INNER_SPLITS = 3  # stability sub-splits; floor class has ~4 members per outer training partition


def _top2_sets(estimator, X_te: np.ndarray) -> np.ndarray:
    """The two careers an estimator would recommend for each row — the product,
    and the thing both stability numbers below are agreement over."""
    return np.argsort(-estimator.predict_proba(X_te), axis=1)[:, :2]


def _pairwise_top2_jaccard(top2_sets: list[np.ndarray]) -> list[float]:
    """Mean per-row top-2 Jaccard for every unordered pair of sub-models.

    One definition, shared by the gated stability number and the reported-only
    reseeded one, so the two can never measure subtly different quantities and be
    compared as if they did not."""
    scores: list[float] = []
    for i in range(len(top2_sets)):
        for j in range(i + 1, len(top2_sets)):
            a, b = top2_sets[i], top2_sets[j]
            inter = np.array([len(set(a[r]) & set(b[r])) for r in range(len(a))], dtype=float)
            union = np.array([len(set(a[r]) | set(b[r])) for r in range(len(a))], dtype=float)
            scores.append(float((inter / union).mean()))
    return scores


def assert_deterministic(name: str, estimator_factory, X, y) -> None:
    """Fit twice on identical data and require bit-identical predict_proba.

    A PRECONDITION of the stability number, not a nicety. cv_oof_and_stability()
    attributes all disagreement between sub-models to the training subset they
    saw. That reading is only valid for an estimator whose refits on identical
    data agree; for one that does not, the number silently mixes in the
    estimator's own randomness, and it would be scored on a strictly noisier
    basis than its competitors. Gate 1's stability threshold must not fire on that
    artifact, so this runs for every candidate before any stability number is
    computed."""
    first = estimator_factory().fit(X, y).predict_proba(X)
    second = estimator_factory().fit(X, y).predict_proba(X)
    if not np.array_equal(first, second):
        disagreeing = int((~np.all(first == second, axis=1)).sum())
        raise SystemExit(
            f"Determinism check FAILED for '{name}': two fits on identical data "
            f"disagree on {disagreeing}/{len(first)} rows (max abs difference "
            f"{float(np.abs(first - second).max()):.3e}). Its top-2 stability would "
            "measure the estimator's own randomness on top of the training-subset "
            "variation the gate intends to measure, so it is not comparable with "
            "the other candidates' and the Gate-1 stability floor must not be "
            "evaluated against it. Fix the estimator's seeding (nn_model.py wires "
            "random_state through every generator a fit draws from) before "
            "trusting any number from this run."
        )


def cv_oof_and_stability(X, y, estimator_factory, n_classes):
    """Pooled OOF probabilities + leakage-free top-2 stability for ONE trained
    scorer configuration. Stability sub-models train on inner resamples of each
    outer training partition and are compared only on that fold's test rows.
    Shared with export_model.py, which revalidates the EXACT exported
    hyperparameter configuration against the Gate-1 thresholds — qualification
    never transfers between configurations unchecked.

    The number this returns is only interpretable for an estimator whose refits on
    identical data agree; it reads ALL sub-model disagreement as training-subset
    variation. main() establishes that with assert_deterministic() before calling
    this. A new caller must do the same — the precondition belongs to the number,
    not to this function's implementation."""
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    oof = np.zeros((len(y), n_classes))
    pair_scores: list[float] = []
    for tr_idx, te_idx in skf.split(X, y):
        oof[te_idx] = estimator_factory().fit(X[tr_idx], y[tr_idx]).predict_proba(X[te_idx])
        inner = StratifiedKFold(n_splits=INNER_SPLITS, shuffle=True, random_state=SEED)
        sub_top2 = []
        for sub_tr, _ in inner.split(X[tr_idx], y[tr_idx]):
            idx = tr_idx[sub_tr]
            sub = estimator_factory().fit(X[idx], y[idx])
            if sub.predict_proba(X[te_idx]).shape[1] != n_classes:
                raise SystemExit(
                    f"A stability sub-model emitted "
                    f"{sub.predict_proba(X[te_idx]).shape[1]} probability columns, "
                    f"expected {n_classes}: a class is missing from an inner resample, "
                    "so its top-2 column indices no longer mean the same careers as "
                    "the other sub-models'. The Jaccard below would silently compare "
                    "mislabelled sets. Raise the per-career label floor "
                    "(dataset_guards.MIN_LABELS_PER_CAREER) rather than reading this "
                    "run's stability."
                )
            sub_top2.append(_top2_sets(sub, X[te_idx]))
        pair_scores.extend(_pairwise_top2_jaccard(sub_top2))
    return oof, float(np.mean(pair_scores))


def reseeded_stability(X, y, estimator_factory_for_seed, seeds=RESEED_SEEDS) -> float:
    """Top-2 agreement across refits that differ ONLY in seed. REPORTED, NEVER GATED.

    The exact complement of cv_oof_and_stability()'s number: there the seed is held
    fixed and the training subset varies, here the subset is held fixed and the seed
    varies. For the two to be *comparable* rather than merely adjacent, everything
    else has to match — so this reuses the same outer folds, the same inner splits,
    and therefore the same training-partition SIZE. Refitting on the full outer
    training partition instead would be the cheaper implementation and a misleading
    number: it would differ from the gated one in training-set size as well as in
    what varies, and the report invites the reader to compare them directly.

    Kept out of the gate deliberately. Folding seed sensitivity into the gated
    number would penalise the network for a property logistic and lightgbm are never
    measured on; dropping it would hide a real property of the architecture — how
    much of a user's recommendation depends on where training happened to start."""
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    pair_scores: list[float] = []
    for tr_idx, te_idx in skf.split(X, y):
        inner = StratifiedKFold(n_splits=INNER_SPLITS, shuffle=True, random_state=SEED)
        for sub_tr, _ in inner.split(X[tr_idx], y[tr_idx]):
            idx = tr_idx[sub_tr]
            reseeded = [
                _top2_sets(estimator_factory_for_seed(s).fit(X[idx], y[idx]), X[te_idx])
                for s in seeds
            ]
            pair_scores.extend(_pairwise_top2_jaccard(reseeded))
    return float(np.mean(pair_scores))


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


def make_small_nn(random_state: int = SEED):
    """Gate-1 configuration of the neural matcher: V0 defaults, hard labels, and a
    fixed random_state — see nn_model.NNClassifier on why the seed is explicit.

    The seed is a parameter so reseeded_stability() varies exactly this
    configuration. A second construction site would let the gated and reported
    numbers describe different networks while being printed side by side."""
    return NNClassifier(random_state=random_state)


LEARNED_FACTORIES = {
    "logistic": make_logistic,
    "lightgbm": make_lightgbm,
    "small_nn": make_small_nn,
}


def main() -> None:
    df, feature_names, careers, meta = load_data()

    # Prerequisite FIRST — silver labels must describe the SAME population the
    # metrics will be computed on. If Phase 0 changed the labeled pool without a
    # Phase-1 rebuild, fail here, before the full CV workload runs. The id-set
    # comparison is bidirectional: a left join alone validates every feature row
    # but never observes silver-only profiles (e.g. a Phase-0 top-up that added
    # rows while preserving existing ids and labels).
    silver = pd.read_parquet(TRAINING_DIR / "silver_labels.parquet")
    feat_ids = set(df["profile_id"])
    silver_ids = set(silver["profile_id"])
    if feat_ids != silver_ids:
        silver_only = sorted(silver_ids - feat_ids)
        feat_only = sorted(feat_ids - silver_ids)
        raise SystemExit(
            "train_features.parquet and silver_labels.parquet contain different "
            f"profile populations ({len(feat_ids)} vs {len(silver_ids)} ids; "
            f"silver-only: {len(silver_only)} e.g. {silver_only[:3]}, "
            f"features-only: {len(feat_only)} e.g. {feat_only[:3]}) — Phase 0 "
            "changed the labeled pool without a Phase-1 rebuild; run "
            "build_training_set.py first."
        )
    aligned = df[["profile_id", "label_top1"]].merge(
        silver[["profile_id", "label_top1", "heuristic_fit_top1"]],
        on="profile_id", how="left", suffixes=("", "_silver"),
    )
    if (aligned["label_top1"] != aligned["label_top1_silver"]).any():
        raise SystemExit(
            "train_features.parquet labels diverge from silver_labels.parquet for "
            "the same profile ids — Phase 0 was regenerated without rebuilding "
            "Phase 1; run build_training_set.py first."
        )
    # heuristic_fit_top1 is the questionnaire-only answer-key winner (no semantic/
    # skill signals) — distinct from the production formula. Prompt versions come
    # from the evaluated table itself, not the silver file.
    heuristic_agree = float((aligned["label_top1"] == aligned["heuristic_fit_top1"]).mean())
    prompt_versions = sorted(df["prompt_version"].unique().tolist())

    X = df[feature_names].to_numpy(dtype=float)
    label_to_idx = {c: i for i, c in enumerate(careers)}
    y = df["label_top1"].map(label_to_idx).to_numpy()
    n_classes = len(careers)

    # Precomputed (train-free) scorer score matrices over ALL rows.
    static_scores = {
        "formula": formula_scores(df, careers),
        "archetype_nn": archetype_scores(df, careers),
    }

    # Static scorers are training-free: their full score matrices ARE the
    # out-of-fold predictions. Trained scorers go through the shared CV helper
    # (identical folds via the fixed seed), which also measures leakage-free
    # top-2 stability.
    oof_scores = {name: s.copy() for name, s in static_scores.items()}

    # Determinism BEFORE stability, for every candidate — the gated stability
    # number reads all sub-model disagreement as training-subset variation, and
    # that reading is only valid for estimators whose refits agree. Running this
    # first means the Gate-1 stability floor can never fire on a measurement
    # artifact (plan Step 3.2). It fails the run rather than warning: a stability
    # number nobody can interpret is worse than no number.
    print(f"determinism check ({', '.join(LEARNED)}) ...")
    for name in LEARNED:
        assert_deterministic(name, LEARNED_FACTORIES[name], X, y)

    stability = {}
    for name in LEARNED:
        print(f"{name}: OOF + top-2 stability ...")
        oof_scores[name], stability[name] = cv_oof_and_stability(
            X, y, LEARNED_FACTORIES[name], n_classes
        )

    # Reported, never gated — see reseeded_stability(). Only the network has a seed
    # whose variation is worth reporting: logistic and lightgbm at these settings
    # are seed-insensitive, which is exactly why the gated number is comparable
    # across all three.
    print("small_nn: reseeded stability (reported, not gated) ...")
    nn_reseeded_stability = reseeded_stability(X, y, make_small_nn)

    results = {}
    for name, s in oof_scores.items():
        # Trained models already emit probabilities; static scorers get a softmax
        # so ECE is computable (flagged as pseudo-probabilities in the report).
        probs = s if name in LEARNED else softmax(s * 10.0)
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
    # (silver alignment, heuristic_agree, and prompt_versions are computed up
    # front, right after load_data — stale inputs fail before the CV workload.)

    # Gate 1 (reframed): calibration + top-2 recommendation stability. The gate is
    # existential — it passes if ANY learned model clears both thresholds; the
    # preferred candidate is the best-calibrated of the qualifiers (falling back to
    # best-calibrated overall for reporting when none qualify).
    qualifiers = [n for n in LEARNED
                  if results[n]["ece"] <= GATE1_MAX_ECE and stability[n] >= GATE1_MIN_TOP2_STABILITY]
    gate1 = bool(qualifiers)
    best_learned = min(qualifiers or LEARNED, key=lambda n: results[n]["ece"])
    best_ece = results[best_learned]["ece"]
    best_stab = stability[best_learned]
    gate_rows = "\n".join(
        f"| {n} | {results[n]['ece']:.3f} | {'yes' if results[n]['ece'] <= GATE1_MAX_ECE else 'NO'} | "
        f"{stability[n]:.3f} | {'yes' if stability[n] >= GATE1_MIN_TOP2_STABILITY else 'NO'} | "
        f"{'QUALIFIES' if n in qualifiers else '—'} |"
        for n in LEARNED
    )

    # Read once and reused for both outputs, so the report and the machine-readable
    # verdict can never disagree about the environment. See env_manifest.py.
    env = environment_manifest()

    # Columns are derived from the scorers actually evaluated — a hardcoded header
    # silently drops a candidate the moment one is added.
    balance_scorers = ["formula", *LEARNED]
    balance_header = " | ".join(f"{n} pred" for n in balance_scorers)
    balance_rows = "\n".join(
        f"| {c} | {label_share[c]:.1%} | "
        + " | ".join(f"{pred_share[n][c]:.1%}" for n in balance_scorers) + " |"
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
predictions. All three trained scorers use class_weight="balanced".

{manifest_markdown(env)}
## Comparison (panel agreement is DESCRIPTIVE only — see caveat a)

| scorer | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE* | top-2 stability |
|---|---|---|---|---|---|---|---|
{fmt_row("formula (production)", results["formula"])} 1.000** |
{fmt_row("archetype_nn (zero-train)", results["archetype_nn"])} 1.000** |
{fmt_row("logistic (balanced)", results["logistic"])} {stability["logistic"]:.3f} |
{fmt_row("lightgbm (balanced)", results["lightgbm"])} {stability["lightgbm"]:.3f} |
{fmt_row("small_nn (balanced, hard labels)", results["small_nn"])} {stability["small_nn"]:.3f} |

*ECE for `formula` and `archetype_nn` is computed on softmax-normalized scores
(pseudo-probabilities) — directional only. Trained models emit real probabilities.
**Static scorers involve no training, so resampling stability is 1.0 by construction.

`small_nn` is scored here on **hard labels**, like every other gate candidate, so
the comparison is like-for-like. The soft-target variant that trains on the panel's
vote distribution is a different objective and remains a Gate-2 challenger in
`train_models.py`; qualification earned here would not transfer to it, which is why
`export_model.py` revalidates the exact shipped configuration against these same
thresholds rather than inheriting a verdict.

## Class balance: label share vs predicted share (over-prediction check)

| career | label share | {balance_header} |
|---|---|{"---|" * len(balance_scorers)}
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

### Determinism precondition (passed — otherwise this report would not exist)

Every **trained** candidate above ({", ".join(f"`{n}`" for n in LEARNED)}) was fitted
twice on identical data and required to produce bit-identical probabilities before
any stability number was computed. (`formula` and `archetype_nn` are training-free,
so there is nothing to check.) The gated stability column reads all sub-model
disagreement as training-subset variation; for an estimator whose own refits
disagree, that reading is false and the number would be strictly noisier than its
competitors'. The run aborts rather than reporting a stability figure the Gate-1
{GATE1_MIN_TOP2_STABILITY} stability threshold could then fire on as a measurement artifact.

### Reseeded stability of `small_nn` — reported, NOT gated

**{nn_reseeded_stability:.3f}** — mean pairwise top-2 Jaccard across
{len(RESEED_SEEDS)} refits that differ **only** in `random_state`. Compare against its
gated **{stability["small_nn"]:.3f}**, where the seed is fixed and the training subset
varies instead.

The two are computed over the same outer folds, the same inner resamples and the
same test rows, so they differ in **what varies and nothing else** — seed at fixed
subset here, subset at fixed seed there. That matching is what makes the
side-by-side reading legitimate: refitting these on the full training partition
would have been cheaper and would have confounded seed sensitivity with a larger
training set.

The reseeded number is deliberately kept out of the gate. Folding seed sensitivity
into it would penalise the network for a property logistic and lightgbm are never
measured on, and the comparison between models would stop being like-for-like.
Dropping it would hide a real property of the architecture: how much of a user's
recommendation depends on where training happened to start.

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
        "metrics": {n: {"ece": results[n]["ece"], "top2_stability": stability[n]} for n in LEARNED},
        "dataset_digest": digest,
        # Additive: downstream readers (train_models.py, export_model.py) address
        # known keys, and a verdict with no environment is a verdict nothing can be
        # diffed against when a later run disagrees.
        "environment": env,
        # Deliberately OUTSIDE "metrics", and named for what it is: nothing may
        # gate on this. Seed sensitivity is a real property of the network, but it
        # is one logistic and lightgbm are never measured on, so admitting it into
        # the gated comparison would stop that comparison being like-for-like.
        "reported_not_gated": {
            "small_nn_reseeded_top2_stability": nn_reseeded_stability,
            "reseed_seeds": list(RESEED_SEEDS),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_GATE1} (passed={gate1}, qualifiers={qualifiers})")


if __name__ == "__main__":
    main()
