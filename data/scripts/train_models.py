"""Phase 3 of the matching-module rework: learned models + Gate 2.

Trains three challengers against the Phase 2 baselines, same outer 5-fold protocol:

    gbt_tuned      LightGBM with per-fold inner 3-fold grid selection (nested CV)
    logistic_tuned logistic regression with inner C selection (nested CV)
    small_nn       torch MLP 38->64->32->6, soft targets from panel votes,
                   class-weighted, dropout + weight decay + early stopping
    two_tower      user tower MLP -> 32-dim; career tower = linear map of the mean
                   panel archetype answers; softmax over scaled cosine similarities

Gate 2: winner by pooled out-of-fold top-2 agreement, tie-broken by ECE after
temperature scaling. FRAMING: all metrics are agreement with the synthetic LLM
panel (silver labels), not expert-validated accuracy.

Outputs: data/training/model_selection.md, data/training/gate2_winner.json
Run from repo root: python data/scripts/train_models.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dataset_guards import assert_min_class_coverage, dataset_digest

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAINING_DIR = REPO_ROOT / "data" / "training"
OUT_MD = TRAINING_DIR / "model_selection.md"
OUT_WINNER = TRAINING_DIR / "gate2_winner.json"

SEED = 42
N_FOLDS = 5
TOP2_VOTE_WEIGHT = 0.4  # a persona's second choice counts this much of a first choice

# Raw-answer feature names in feature_builder order (q1, q2, …). Derived from the
# metadata's feature_names so the question set stays a single source of truth —
# adding questions to the bank never needs a change here.
_QID_RE = re.compile(r"q\d+$")

GBT_GRID = list(product([200, 400], [0.03, 0.07], [7, 15], [3, 10]))
LOGISTIC_C_GRID = [0.05, 0.25, 1.0, 4.0]

rng = np.random.default_rng(SEED)
torch.manual_seed(SEED)


# ---------------------------------------------------------------- data
def load_data():
    df = pd.read_parquet(TRAINING_DIR / "train_features.parquet")
    meta = json.loads((TRAINING_DIR / "dataset_metadata.json").read_text(encoding="utf-8"))
    silver = pd.read_parquet(TRAINING_DIR / "silver_labels.parquet")
    arch = pd.read_parquet(TRAINING_DIR / "archetypes_synthetic.parquet")

    feature_names = meta["feature_names"]
    careers = [n[: -len("_fit")] for n in feature_names if n.endswith("_fit")]
    question_ids = [n for n in feature_names if _QID_RE.fullmatch(n)]
    label_to_idx = {c: i for i, c in enumerate(careers)}

    # Guard before any training: nested CV and the NN validation split need every
    # class present in every outer-fold training partition (>= 5 labels each).
    assert_min_class_coverage(df["label_top1"], careers, context="train_features.parquet")

    X = df[feature_names].to_numpy(dtype=np.float32)
    y = df["label_top1"].map(label_to_idx).to_numpy()

    # Soft targets from the panel's individual votes (top1=1.0, top2=0.4 each).
    votes = silver.set_index("profile_id")["votes_json"]
    soft = np.zeros((len(df), len(careers)), dtype=np.float32)
    for i, pid in enumerate(df["profile_id"]):
        for v in json.loads(votes.loc[pid]):
            soft[i, label_to_idx[v["top1"]]] += 1.0
            if v.get("top2") in label_to_idx:
                soft[i, label_to_idx[v["top2"]]] += TOP2_VOTE_WEIGHT
    soft /= soft.sum(axis=1, keepdims=True)

    arch_mat = np.stack([
        arch[arch.career_id == cid][question_ids].mean().to_numpy(dtype=np.float32)
        for cid in careers
    ])
    return df, X, y, soft, careers, arch_mat, meta


def class_weights(y: np.ndarray, n_classes: int) -> np.ndarray:
    counts = np.bincount(y, minlength=n_classes).astype(float)
    w = counts.sum() / np.maximum(counts, 1) / n_classes
    return w


# ---------------------------------------------------------------- metrics
def rank_metrics(probs: np.ndarray, y: np.ndarray) -> dict:
    order = np.argsort(-probs, axis=1)
    ranks = np.array([int(np.where(order[i] == y[i])[0][0]) for i in range(len(y))])
    pred = order[:, 0]
    per_class = {}
    for c in range(probs.shape[1]):
        m = y == c
        per_class[c] = float((pred[m] == c).mean()) if m.any() else float("nan")
    return {
        "top1": float((ranks == 0).mean()),
        "top2": float((ranks <= 1).mean()),
        "top3": float((ranks <= 2).mean()),
        "mrr": float((1.0 / (ranks + 1)).mean()),
        "balanced_top1": float(np.nanmean(list(per_class.values()))),
        "per_class": per_class,
    }


def ece(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    pred = probs.argmax(axis=1)
    conf = probs[np.arange(len(probs)), pred]
    correct = (pred == y).astype(float)
    out, bins = 0.0, np.linspace(0, 1, n_bins + 1)
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf >= lo) & ((conf < hi) if hi < 1.0 else (conf <= hi))
        if m.any():
            out += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(out)


def temperature_scale(probs: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """Grid-fit a single temperature on pooled OOF probabilities (prototype-grade:
    fitted on the same OOF pool it is evaluated on; redo on gold labels later)."""
    logits = np.log(np.clip(probs, 1e-9, 1.0))
    best_t, best_nll = 1.0, np.inf
    for t in np.linspace(0.25, 4.0, 76):
        z = logits / t
        z = z - z.max(axis=1, keepdims=True)
        p = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
        nll = -np.log(np.clip(p[np.arange(len(y)), y], 1e-9, 1)).mean()
        if nll < best_nll:
            best_nll, best_t = nll, float(t)
    z = logits / best_t
    z = z - z.max(axis=1, keepdims=True)
    p = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
    return p, best_t


# ---------------------------------------------------------------- 3a nested-CV tuned models
def fit_gbt(params, Xtr, ytr):
    n_est, lr, leaves, mcs = params
    return LGBMClassifier(
        n_estimators=n_est, learning_rate=lr, num_leaves=leaves, min_child_samples=mcs,
        subsample=0.9, colsample_bytree=0.8, class_weight="balanced",
        random_state=SEED, verbose=-1,
    ).fit(Xtr, ytr)


def top2_of(model, Xv, yv) -> float:
    probs = model.predict_proba(Xv)
    order = np.argsort(-probs, axis=1)[:, :2]
    return float(np.mean([yv[i] in order[i] for i in range(len(yv))]))


def oof_gbt_tuned(X, y):
    oof = np.zeros((len(y), len(np.unique(y))))
    chosen = []
    outer = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    for tr, te in outer.split(X, y):
        inner = StratifiedKFold(3, shuffle=True, random_state=SEED)
        best_p, best_s = None, -1.0
        for params in GBT_GRID:
            scores = []
            for itr, ival in inner.split(X[tr], y[tr]):
                m = fit_gbt(params, X[tr][itr], y[tr][itr])
                scores.append(top2_of(m, X[tr][ival], y[tr][ival]))
            s = float(np.mean(scores))
            if s > best_s:
                best_s, best_p = s, params
        chosen.append(best_p)
        oof[te] = fit_gbt(best_p, X[tr], y[tr]).predict_proba(X[te])
    return oof, chosen


def oof_logistic_tuned(X, y):
    oof = np.zeros((len(y), len(np.unique(y))))
    chosen = []
    outer = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    for tr, te in outer.split(X, y):
        inner = StratifiedKFold(3, shuffle=True, random_state=SEED)
        best_c, best_s = None, -1.0
        for C in LOGISTIC_C_GRID:
            scores = []
            for itr, ival in inner.split(X[tr], y[tr]):
                m = make_pipeline(
                    StandardScaler(),
                    LogisticRegression(C=C, max_iter=5000, class_weight="balanced", random_state=SEED),
                ).fit(X[tr][itr], y[tr][itr])
                scores.append(top2_of(m, X[tr][ival], y[tr][ival]))
            s = float(np.mean(scores))
            if s > best_s:
                best_s, best_c = s, C
        chosen.append(best_c)
        m = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=best_c, max_iter=5000, class_weight="balanced", random_state=SEED),
        ).fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])
    return oof, chosen


# ---------------------------------------------------------------- 3b small NN (soft targets)
class SmallNN(nn.Module):
    def __init__(self, d_in: int, n_classes: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_in, 64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(32, n_classes),
        )

    def forward(self, x):
        return self.net(x)


def train_nn_fold(Xtr, soft_tr, ytr, Xte, n_classes):
    # Standardize on train stats only.
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-8
    Xtr_s, Xte_s = (Xtr - mu) / sd, (Xte - mu) / sd
    itr, ival = train_test_split(
        np.arange(len(Xtr_s)), test_size=0.15, stratify=ytr, random_state=SEED
    )
    w = class_weights(ytr, n_classes)
    sample_w = torch.tensor(w[ytr], dtype=torch.float32)

    model = SmallNN(Xtr.shape[1], n_classes)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    Xt = torch.tensor(Xtr_s)
    St = torch.tensor(soft_tr)

    def loss_on(idx, training):
        model.train(training)
        logits = model(Xt[idx])
        logp = torch.log_softmax(logits, dim=1)
        # soft-target cross-entropy, class-weighted per sample
        per = -(St[idx] * logp).sum(dim=1) * sample_w[idx]
        return per.mean()

    best_state, best_val, patience = None, np.inf, 0
    for epoch in range(400):
        perm = torch.randperm(len(itr))
        for b in perm.split(32):
            opt.zero_grad()
            loss = loss_on(torch.tensor(itr)[b], training=True)
            loss.backward()
            opt.step()
        with torch.no_grad():
            val = float(loss_on(torch.tensor(ival), training=False))
        if val < best_val - 1e-4:
            best_val, best_state, patience = val, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 30:
                break
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        return torch.softmax(model(torch.tensor(Xte_s)), dim=1).numpy()


# ---------------------------------------------------------------- 3c two-tower
class TwoTower(nn.Module):
    def __init__(self, d_in: int, arch_mat: np.ndarray, d_emb: int = 32):
        super().__init__()
        self.user = nn.Sequential(
            nn.Linear(d_in, 64), nn.ReLU(), nn.Dropout(0.3), nn.Linear(64, d_emb),
        )
        self.career_in = torch.tensor(arch_mat)  # (n_careers, 10) mean archetype answers
        self.career = nn.Linear(arch_mat.shape[1], d_emb)
        self.scale = nn.Parameter(torch.tensor(10.0))

    def forward(self, x):
        u = nn.functional.normalize(self.user(x), dim=1)
        c = nn.functional.normalize(self.career(self.career_in), dim=1)
        return self.scale * u @ c.T  # scaled cosine logits


def train_two_tower_fold(Xtr, ytr, Xte, arch_mat, n_classes):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-8
    Xtr_s, Xte_s = (Xtr - mu) / sd, (Xte - mu) / sd
    itr, ival = train_test_split(
        np.arange(len(Xtr_s)), test_size=0.15, stratify=ytr, random_state=SEED
    )
    w = torch.tensor(class_weights(ytr, n_classes), dtype=torch.float32)
    model = TwoTower(Xtr.shape[1], arch_mat)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    Xt, yt = torch.tensor(Xtr_s), torch.tensor(ytr)
    ce = nn.CrossEntropyLoss(weight=w)

    best_state, best_val, patience = None, np.inf, 0
    for epoch in range(400):
        model.train()
        perm = torch.randperm(len(itr))
        for b in perm.split(32):
            idx = torch.tensor(itr)[b]
            opt.zero_grad()
            loss = ce(model(Xt[idx]), yt[idx])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val = float(ce(model(Xt[torch.tensor(ival)]), yt[torch.tensor(ival)]))
        if val < best_val - 1e-4:
            best_val, best_state, patience = val, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 30:
                break
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        return torch.softmax(model(torch.tensor(Xte_s)), dim=1).numpy()


# ---------------------------------------------------------------- main
def main() -> None:
    df, X, y, soft, careers, arch_mat, meta = load_data()
    n_classes = len(careers)
    outer = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)

    print("3a: nested-CV tuned LightGBM ...")
    oof_gbt, gbt_params = oof_gbt_tuned(X, y)
    print("3a: nested-CV tuned logistic ...")
    oof_log, log_params = oof_logistic_tuned(X, y)

    print("3b: small NN (soft targets) ...")
    oof_nn = np.zeros((len(y), n_classes))
    for tr, te in outer.split(X, y):
        oof_nn[te] = train_nn_fold(X[tr], soft[tr], y[tr], X[te], n_classes)

    print("3c: two-tower (archetype-seeded) ...")
    oof_tt = np.zeros((len(y), n_classes))
    for tr, te in outer.split(X, y):
        oof_tt[te] = train_two_tower_fold(X[tr], y[tr], X[te], arch_mat, n_classes)

    models = {
        "gbt_tuned": oof_gbt,
        "logistic_tuned": oof_log,
        "small_nn": oof_nn,
        "two_tower": oof_tt,
    }

    results = {}
    for name, probs in models.items():
        m = rank_metrics(probs, y)
        m["ece_raw"] = ece(probs, y)
        scaled, t = temperature_scale(probs, y)
        m["ece_scaled"] = ece(scaled, y)
        m["temperature"] = t
        results[name] = m

    # Gate 2: top-2 primary, ECE-after-scaling tiebreak (within 0.01 of top-2).
    best_top2 = max(r["top2"] for r in results.values())
    contenders = [n for n, r in results.items() if best_top2 - r["top2"] <= 0.01]
    winner = min(contenders, key=lambda n: results[n]["ece_scaled"])

    # Deployment selection, explicit: the serving path (matcher_model.py) is
    # dependency-free LINEAR inference with exact attribution, so only logistic is
    # deployable — and only if it QUALIFIED under Gate 1 (calibration + stability).
    # A model the gate rejected must never become deployable just because the
    # Gate-2 winner has no serving path; export refuses when deployable is null.
    digest = dataset_digest(df, meta["feature_names"])
    gate1_path = TRAINING_DIR / "gate1_verdict.json"
    if not gate1_path.exists():
        raise SystemExit(f"{gate1_path} not found — run evaluate_matchers.py (Phase 2) first.")
    gate1 = json.loads(gate1_path.read_text(encoding="utf-8"))
    if gate1.get("dataset_digest") != digest:
        raise SystemExit(
            "gate1_verdict.json was computed on a different dataset build — rerun "
            "evaluate_matchers.py (Phase 2) on the current train_features.parquet first."
        )
    # Gate-1 qualifier names are the Phase-2 default-config scorers; "logistic"
    # is the qualifier corresponding to the servable logistic_tuned architecture.
    logistic_qualified = "logistic" in gate1.get("qualifiers", [])
    if winner == "logistic_tuned" and logistic_qualified:
        deployable = "logistic_tuned"
        deployable_reason = "gate2 winner is servable and Gate-1-qualified"
    elif logistic_qualified:
        deployable = "logistic_tuned"
        deployable_reason = (
            f"gate2 winner '{winner}' has no serving path (matcher_model.py is linear-only "
            "with exact attribution — the Phase-4 explainability requirement); logistic is "
            "the Gate-1-qualified deployable selection"
        )
    else:
        deployable = None
        deployable_reason = (
            "no servable model qualified under Gate 1 "
            f"(qualifiers={gate1.get('qualifiers', [])}, servable=logistic only) — "
            "nothing is deployable; export_model.py will refuse"
        )

    # Phase-2 reference recomputed on THIS dataset (a hardcoded copy of a previous
    # run's numbers silently went stale when the dataset was regenerated).
    from evaluate_matchers import formula_scores
    f_order = np.argsort(-formula_scores(df, careers), axis=1)
    formula_top2_ref = float(np.mean([y[i] in f_order[i, :2] for i in range(len(y))]))

    def fmt(name, m):
        return (f"| {name} | {m['top1']:.3f} | {m['top2']:.3f} | {m['top3']:.3f} | "
                f"{m['mrr']:.3f} | {m['balanced_top1']:.3f} | {m['ece_raw']:.3f} | "
                f"{m['ece_scaled']:.3f} | {m['temperature']:.2f} |")

    per_class = []
    for name, m in results.items():
        rows = "\n".join(f"| {careers[c]} | {v:.2f} |" for c, v in m["per_class"].items())
        per_class.append(f"### {name}\n\n| career | top-1 recall |\n|---|---|\n{rows}")

    report = f"""# Model Selection — Phase 3 / Gate 2

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Calibration (temperature) fitted on pooled
> out-of-fold predictions — prototype-grade; redo on gold labels before trusting
> displayed percentages.

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Dataset: {len(df)} rows, feature `{meta["feature_version"]}`, seed {SEED},
outer {N_FOLDS}-fold stratified CV (same folds as Phase 2).
Phase 2 reference (recomputed on THIS dataset, not hardcoded from a previous run):
production-formula top-2 agreement {formula_top2_ref:.3f}; full Phase-2 comparison
in baseline_evaluation.md.

## Comparison (pooled out-of-fold)

| model | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE raw | ECE scaled | T |
|---|---|---|---|---|---|---|---|---|
{fmt("gbt_tuned (3a)", results["gbt_tuned"])}
{fmt("logistic_tuned (3a)", results["logistic_tuned"])}
{fmt("small_nn soft-targets (3b)", results["small_nn"])}
{fmt("two_tower archetype-seeded (3c)", results["two_tower"])}

Chosen hyperparameters per outer fold:
- gbt (n_estimators, lr, num_leaves, min_child_samples): {gbt_params}
- logistic C: {log_params}

## Per-class top-1 recall

{chr(10).join(per_class)}

## Gate 2 verdict

**Winner: `{winner}`** — top-2 {results[winner]["top2"]:.3f}, ECE after temperature
scaling {results[winner]["ece_scaled"]:.3f} (T={results[winner]["temperature"]:.2f}).
Selection rule: highest top-2; ties within 0.01 broken by scaled ECE.

## Deployment selection

**Deployable winner: `{deployable or "NONE"}`** — {deployable_reason}.
export_model.py refuses to export unless this names the architecture it produces
(and refuses outright when it is NONE), so the served artifact and this report
cannot silently disagree — and a Gate-1-rejected model can never ship.

Notes:
- The soft-target NN consumes the panel vote distribution (top1=1.0, top2={TOP2_VOTE_WEIGHT});
  the other models train on hard consensus labels with class weights.
- two_tower remains the only architecture that admits a new career without
  retraining (one archetype vector); keep it as future work even if it loses here.
"""
    OUT_MD.write_text(report, encoding="utf-8")
    OUT_WINNER.write_text(json.dumps({
        "winner": winner,
        "deployable": deployable,
        "deployable_reason": deployable_reason,
        # Which dataset build this selection was computed on; export_model.py
        # refuses to export against a different build so a regenerated (or
        # hand-edited) train_features.parquet can't be paired with a stale
        # selection. The digest hashes the actual features+labels content —
        # sidecar metadata alone can't detect a replaced table.
        "dataset_digest": digest,
        "dataset_fingerprint": {"created_at": meta["created_at"], "n_rows": len(df)},
        "gate1": {"passed": gate1["passed"], "qualifiers": gate1.get("qualifiers", [])},
        "metrics": {k: v for k, v in results[winner].items() if k != "per_class"},
        "gbt_params_per_fold": gbt_params,
        "logistic_C_per_fold": log_params,
        "feature_version": meta["feature_version"],
        "seed": SEED,
        "label_source": "synthetic_llm",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
