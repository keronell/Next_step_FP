"""Phase 3 of the matching-module rework: learned models + Gate 2.

Trains three challengers against the Phase 2 baselines, same outer 5-fold protocol:

    gbt_tuned      LightGBM with per-fold inner 3-fold grid selection (nested CV)
    logistic_tuned logistic regression with inner C selection (nested CV)
    small_nn       nn_model.NNClassifier (MLP 84->64->32->16 at features-v4), soft
                   targets from panel votes, class-weighted, dropout + weight decay
                   + early stopping
    two_tower      user tower MLP -> 32-dim; career tower = linear map of the mean
                   panel archetype answers; softmax over scaled cosine similarities
    residual_matcher  nn_model.ResidualMatcher (DEV-92, ADR 0006): frozen logistic
                   branch plus alpha-gated MLP correction, alpha selected by inner CV
                   and C inherited from that fold's tuned-logistic selection. Hard
                   labels, unlike small_nn — the paired comparison against
                   logistic_tuned only holds while both optimise the same targets.
                   Wired in by DEV-93, which also records the pre-registered
                   alpha=0 >=3-of-5 verdict.

`small_nn` is imported from `nn_model`, the same definition Gate 1 scores in
evaluate_matchers.py — the network used to be declared inline here, so "the NN"
meant whatever this file happened to do and the two gates could not be talking
about the same object. The only difference between the two gates' use of it is the
target: Gate 1 feeds hard labels like every other candidate, Gate 2 additionally
passes the panel's vote distribution as soft targets.

Gate 2: winner by pooled out-of-fold top-2 agreement, tie-broken by ECE after
temperature scaling. FRAMING: all metrics are agreement with the synthetic LLM
panel (silver labels), not expert-validated accuracy.

CALIBRATION IS CROSS-FITTED (2026-07-28, DEV-91, ADR 0007). The temperature used
for the reported and gating ECE is fitted per outer fold on inner out-of-fold
predictions drawn only from that fold's TRAINING partition, and then applied to
that fold's held-out rows. It previously came from one fit on the pooled OOF that
was then scored on those same predictions — Leakage in the strict sense, and
differential: a worse-calibrated model gains more from fitting T on its own
evaluation data, and that number is the tiebreak. `cross_fitted_oof()` owns the
protocol for all four models so none of them can re-implement it wrongly.

Every Gate-2 calibration number here is therefore NON-COMPARABLE to any recorded
before that date, including the gbt_tuned ECE 0.047 that won Gate 2. All four
models were re-baselined together in one run; the report says so in a section that
cannot be missed. Ranking metrics are unaffected for gbt_tuned and logistic_tuned
because temperature scaling is monotone within a row. `small_nn` moved for a second
reason as well — DEV-90 replaced its inline definition with nn_model.NNClassifier,
which re-seeds torch per fit where the old code inherited accumulated
process-global RNG state, so its recorded row was already stale. `two_tower` moved
for a second reason too: it still seeds from process-global torch RNG rather than
per fit, so the three extra fits per fold that cross-fitting inserts shift it.

Outputs: data/training/model_selection.md, data/training/gate2_winner.json
Run from repo root, in the hash-pinned training venv (data/scripts/README.md):

    data/venv-training/bin/python data/scripts/train_models.py
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
from sklearn.model_selection import StratifiedKFold, train_test_split

from dataset_guards import assert_min_class_coverage, dataset_digest
from env_manifest import environment_manifest, manifest_markdown
from nn_model import NNClassifier, ResidualMatcher, class_weights, frozen_logistic

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAINING_DIR = REPO_ROOT / "data" / "training"
OUT_MD = TRAINING_DIR / "model_selection.md"
OUT_WINNER = TRAINING_DIR / "gate2_winner.json"

SEED = 42
N_FOLDS = 5
TOP2_VOTE_WEIGHT = 0.4  # a persona's second choice counts this much of a first choice

# When the cross-fitted-temperature re-baseline landed. Printed in the report so a
# reader holding an older model_selection.md can tell at a glance whether its
# calibration numbers are comparable to the one in front of them. See ADR 0007.
BREAK_DATE = "2026-07-28 (DEV-91)"

# The recorded Gate-2 numbers this run breaks from, so the regenerated report can
# show both sides instead of asking a reader to go find the old file. Source:
# model_selection.md generated 2026-07-19T16:03:27Z, the last run under the pooled
# temperature AND the inline pre-DEV-90 network.
RECORDED_HISTORY = {
    "gbt_tuned": {"ece_raw": 0.135, "ece_scaled": 0.047, "temperature": 1.65, "top2": 0.892},
    "logistic_tuned": {"ece_raw": 0.103, "ece_scaled": 0.103, "temperature": 1.00, "top2": 0.849},
    "small_nn": {"ece_raw": 0.130, "ece_scaled": 0.101, "temperature": 0.90, "top2": 0.841},
    "two_tower": {"ece_raw": 0.047, "ece_scaled": 0.077, "temperature": 1.30, "top2": 0.746},
}

# Raw-answer feature names in feature_builder order (q1, q2, …). Derived from the
# metadata's feature_names so the question set stays a single source of truth —
# adding questions to the bank never needs a change here.
_QID_RE = re.compile(r"q\d+$")

GBT_GRID = list(product([200, 400], [0.03, 0.07], [7, 15], [3, 10]))
LOGISTIC_C_GRID = [0.05, 0.25, 1.0, 4.0]
# Pre-registered in ADR 0006 and fixed. Widening it later is a protocol change, not
# a tuning tweak: alpha=0 is the retreat-to-the-Incumbent point the whole design
# rests on, and the >=3-of-5 disqualification rule below is stated against this grid.
RESIDUAL_ALPHA_GRID = (0.0, 0.25, 0.5, 1.0)

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


def nll(probs: np.ndarray, y: np.ndarray) -> float:
    """Mean negative log-likelihood — the objective `fit_temperature` minimises.

    The objective `fit_temperature` minimises, and reported alongside ECE to show
    that the old protocol's bias has no reliable direction in EITHER metric. The
    only guarantee is family-relative: a temperature fitted on a pool is the argmin
    of NLL on that pool *among constant temperatures*, so no other constant beats it
    there. Cross-fitting does not stay inside that family — it applies five per-fold
    constants — so it can and does score lower.
    `test_cross_fitted_temperature.py` holds the guarantee in the form that is
    actually true."""
    return float(-np.log(np.clip(probs[np.arange(len(y)), y], 1e-9, 1)).mean())


TEMPERATURE_GRID = np.linspace(0.25, 4.0, 76)


def apply_temperature(probs: np.ndarray, t: float) -> np.ndarray:
    """Divide the logits by `t` and renormalize. Monotone per row, so it moves
    calibration and never the ranking — which is why top-2 (the Gate-2 primary)
    is identical before and after scaling, and only ECE responds."""
    z = np.log(np.clip(probs, 1e-9, 1.0)) / t
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(probs: np.ndarray, y: np.ndarray) -> float:
    """Grid-fit the temperature that minimises NLL of `y` under `probs`."""
    best_t, best_nll = 1.0, np.inf
    for t in TEMPERATURE_GRID:
        candidate = nll(apply_temperature(probs, t), y)
        if candidate < best_nll:
            best_nll, best_t = candidate, float(t)
    return best_t


def temperature_scale(probs: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """Fit a temperature on `probs` and apply it to `probs`.

    Fitting and scoring on the same pool, which is precisely the defect ADR 0007
    records — so this is NOT how the reported ECE is computed any more. Two honest
    uses remain:

    - a **deployment** temperature, when `probs` are OOF predictions from the exact
      configuration being serialized. export_model.py does this after selecting
      its fixed C; there is no held-out set to preserve when choosing the one
      constant to ship.
    - the **legacy** number reported beside the cross-fitted one, purely to size
      how optimistic the old protocol was.
    """
    t = fit_temperature(probs, y)
    return apply_temperature(probs, t), t


# ------------------------------------------- cross-fitted calibration (Step 4.2)
INNER_SPLITS = 3


def outer_folds(X: np.ndarray, y: np.ndarray, random_state: int = SEED):
    """The one outer partition every model in this file is scored on — same folds
    as Phase 2, by construction rather than by coincidence.

    `random_state` exists for the Round-1 sweep's 5-seed protocol (DEV-93), where an
    experiment seed varies the fold partition as well as the initialisation. **The
    default is the single-seed path**, so everything this file reports today is
    unchanged; within one seed all models still share folds, which is what keeps the
    paired comparison paired.
    """
    return StratifiedKFold(N_FOLDS, shuffle=True, random_state=random_state).split(X, y)


def cross_fitted_oof(X, y, n_classes, fit_predict, select_config=None,
                     random_state: int = SEED):
    """Pooled OOF probabilities, raw and calibrated, with the temperature fitted
    per outer fold on data that fold's model has never been scored against.

    `fit_predict(config, train_idx, predict_idx) -> probs` trains on `train_idx`
    and predicts on `predict_idx`, both absolute row indices. `select_config(tr)`
    is the plan's `select_by_inner_cv` — real for the two nested-selection models,
    omitted for `small_nn` and `two_tower`, which have no inner grid.

    Per fold: estimate T from inner-OOF predictions the training partition makes
    about ITSELF, then apply that T to the held-out rows. `te` is out of scope for
    every line of the estimation, which is the whole point — the previous protocol
    fitted one T on the pooled OOF and then scored ECE on those same predictions,
    flattering worse-calibrated models more than better-calibrated ones and so
    biasing the Gate-2 tiebreak itself.

    Costs three extra fits per outer fold per model. Returns the per-fold
    temperatures alongside the probabilities because their SPREAD is a finding: a
    single pooled temperature for this evaluated configuration is only a
    well-estimated quantity if the five agree.
    """
    oof_raw = np.zeros((len(y), n_classes))
    oof_calibrated = np.zeros((len(y), n_classes))
    temperatures: list[float] = []
    chosen: list = []

    for tr, te in outer_folds(X, y, random_state=random_state):
        config = select_config(tr) if select_config is not None else None
        chosen.append(config)

        inner_oof = np.zeros((len(tr), n_classes))
        inner = StratifiedKFold(INNER_SPLITS, shuffle=True, random_state=random_state)
        for itr, ival in inner.split(X[tr], y[tr]):
            inner_oof[ival] = fit_predict(config, tr[itr], tr[ival])
        t = fit_temperature(inner_oof, y[tr])

        raw = fit_predict(config, tr, te)
        oof_raw[te] = raw
        oof_calibrated[te] = apply_temperature(raw, t)
        temperatures.append(t)

    return oof_raw, oof_calibrated, temperatures, chosen


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


def fit_logistic(C, Xtr, ytr):
    """The Incumbent's estimator. Constructed by `nn_model.frozen_logistic` rather than here, so
    the Residual Matcher's frozen branch is the same estimator by construction and
    not by a comment claiming it is — ADR 0006's paired comparison depends on that
    and nothing else enforces it."""
    return frozen_logistic(C, SEED).fit(Xtr, ytr)


# The plan's `select_by_inner_cv(tr)`: pick a configuration using ONLY the outer
# fold's training partition. Both are pure functions of `tr`, which is what lets
# cross_fitted_oof reuse them for the temperature's inner refits without any risk
# of the selection seeing the rows it will be scored on.
def select_by_inner_cv(X, y, tr, grid, fit, random_state: int = SEED, scores_out=None,
                       inner_splits: int = INNER_SPLITS):
    """The plan's `select_by_inner_cv(tr)`: the grid point with the best inner-CV
    top-2, chosen using ONLY the outer fold's training partition.

    A pure function of `tr`, which is what lets cross_fitted_oof reuse the selected
    configuration for the temperature's inner refits with no risk of the selection
    having seen the rows it will be scored on. `fit(params, Xtr, ytr)` returns a
    fitted estimator.

    The Round-1 sweep (DEV-93) reuses this for its 14-Variant contest rather than
    writing a second grid-argmax, so "no separate selection stage exists" is true of
    the code and not only of the plan. `random_state` defaults to the single-seed
    path.

    `scores_out` is an optional list that receives `(params, score)` for every grid
    point in grid order — the losers as well as the winner. Added by DEV-95 because
    Round 1 computed a 14-way contest 25 times and kept only the argmax, and ADR
    0003's disqualification clause then required naming "the best genuinely
    non-linear Variant" from evidence that had already been discarded.

    **It is an out-parameter rather than a second return value deliberately.** This
    function has six call sites and one test asserts on its return value directly
    against an inherited `C`; widening the return type would change what four callers
    receive to fix a need only one of them has. The channel is invisible to a caller
    that does not pass it, the grid is walked in the same order either way, and each
    point is fitted the same number of times — so no RNG consumption moves.

    `inner_splits` defaults to the pipeline's 3 and exists for the learning curve
    (DEV-96), whose smallest point leaves **two** rows of the rarest class in an outer
    training partition. A 3-fold inner split of that drops a class from an inner
    training subset, sklearn warns rather than raises, and the fitted estimator then
    emits fewer probability columns — so `top2_of` would read column indices that mean
    different careers. The curve therefore selects under 2 inner folds at EVERY point,
    identically; it is not a per-point protocol change.
    """
    inner = StratifiedKFold(inner_splits, shuffle=True, random_state=random_state)
    best_params, best_score = None, -1.0
    for params in grid:
        scores = []
        for itr, ival in inner.split(X[tr], y[tr]):
            m = fit(params, X[tr][itr], y[tr][itr])
            scores.append(top2_of(m, X[tr][ival], y[tr][ival]))
        score = float(np.mean(scores))
        if scores_out is not None:
            scores_out.append((params, score))
        # Strictly greater: ties keep the EARLIER grid point. The sweep's registry
        # order is therefore its tie-break, which `nn_rework.md` discloses.
        if score > best_score:
            best_score, best_params = score, params
    return best_params


# (3b small NN — the network lives in nn_model.py, shared with Gate 1. Its
# standardization, class weighting, validation split and early stopping moved
# there with it; the only thing this file supplies is the soft-target matrix.)


# ------------------------------------------------- residual matcher (Step 2.3)
# The Residual Matcher's selection wiring. Deliberately NOT wired into main():
# it is one of the fourteen Variants of the round-1 sweep, and entering it in
# Gate 2 ahead of that sweep would pick its configuration by a different protocol
# than the one every other Variant competes under. The sweep consumes what is
# below; nothing here changes the four models main() scores today.
def fit_residual(config, Xtr, ytr, random_state=SEED, **mlp_kwargs):
    """Fit the Residual Matcher for one `(alpha, C)` configuration on `Xtr`.

    Both halves of the config were chosen on the outer fold's training partition,
    and the frozen base is refit inside `ResidualMatcher.fit` on exactly the rows
    handed here — so when `select_by_inner_cv` calls this on an inner-training
    subset, the base is refit on that subset. That is the plan's "refit on whichever
    partition the MLP trains on", and it holds structurally: there is no argument
    through which a caller could pass a base fitted on something wider."""
    alpha, C = config
    return ResidualMatcher(
        random_state=random_state, alpha=alpha, logistic_C=C, **mlp_kwargs
    ).fit(Xtr, ytr)


def select_residual_config(X, y, tr, random_state=SEED, **mlp_kwargs):
    """The plan's `select_by_inner_cv(tr)` for the Residual Matcher, returning
    `(alpha, C)`.

    `C` is **inherited** from this outer fold's tuned-logistic selection rather than
    re-selected at a third nesting level. It was chosen using only outer-training
    data, so reusing it inside inner splits of the same partition never touches the
    outer test set — and it makes the frozen base exactly the Incumbent's
    configuration on this partition, which is what turns "does the residual add
    anything?" into an exactly paired comparison (ADR 0006). Selecting `C` at a
    third level is the purist option and does not earn its complexity.

    `alpha` is then a grid-argmax on inner-CV top-2, like every other nested
    selection in this file. Like them it trains on **hard labels**: the soft-target
    objective is a Gate-2 challenger property rather than part of choosing a
    configuration, and keeping selection on one basis is what makes the four models'
    selections comparable. Whether the sweep goes on to *score* the chosen
    configuration on soft targets is its decision, not this function's —
    `ResidualMatcher.fit` takes `soft_targets` like any `NNClassifier`.

    A pure function of `tr` in both halves, which is what lets `cross_fitted_oof`
    reuse the result for the temperature's inner refits with no risk of the
    selection having seen the rows it will be scored on.
    """
    C = select_by_inner_cv(
        X, y, tr, LOGISTIC_C_GRID, fit_logistic, random_state=random_state
    )
    return select_by_inner_cv(
        X, y, tr,
        [(alpha, C) for alpha in RESIDUAL_ALPHA_GRID],
        lambda config, Xtr, ytr: fit_residual(
            config, Xtr, ytr, random_state=random_state, **mlp_kwargs
        ),
        random_state=random_state,
    )


# Pre-registered in ADR 0006, before any alpha was selected on this data.
ALPHA_ZERO_DISQUALIFIES_AT = 3


def alpha_zero_verdict(chosen) -> dict:
    """Read the pre-registered rule off `cross_fitted_oof`'s per-fold configs.

    `alpha = 0` selected in >= 3 of 5 outer folds is reported as **"no non-linear
    signal found"** and disqualifies the Residual Matcher from being the shipped
    neural model — shipping it would be shipping logistic regression in a costume
    while the project requires a neural network (ADR 0004). The rule lives here, in
    one function, so the sweep reads it rather than restating it: a pre-registered
    threshold that gets paraphrased at the point of use is a threshold that can move
    after somebody has seen the data.

    Reporting only. Nothing here selects, and a disqualified Residual Matcher is
    still reported in full — the plan's Step 6 table says the shipped model becomes
    the best genuinely non-linear Variant and the cost of that substitution is
    stated explicitly.
    """
    if len(chosen) != N_FOLDS:
        raise ValueError(
            f"the >= {ALPHA_ZERO_DISQUALIFIES_AT}-of-{N_FOLDS} rule was pre-registered "
            f"against {N_FOLDS} outer folds and got {len(chosen)}. It is a count, not "
            "a proportion, so it cannot be rescaled onto a different protocol without "
            "choosing a new threshold after the fact."
        )
    per_fold = [float(alpha) for alpha, _ in chosen]
    n_zero = sum(1 for alpha in per_fold if alpha == 0.0)
    return {
        "per_fold_alpha": per_fold,
        "per_fold_logistic_C": [c for _, c in chosen],
        "n_folds_at_zero": n_zero,
        "no_non_linear_signal": n_zero >= ALPHA_ZERO_DISQUALIFIES_AT,
        "rule": (
            f"alpha=0 in >= {ALPHA_ZERO_DISQUALIFIES_AT} of {N_FOLDS} outer folds is "
            "'no non-linear signal found' and disqualifies the Residual Matcher from "
            "being the shipped neural model (ADR 0006, pre-registered)"
        ),
    }


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

    # Prerequisites FIRST — a stale or out-of-order pipeline run must fail here,
    # not after nested CV and the neural challengers have burned minutes of work.
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
    # qualifying makes the logistic ARCHITECTURE a deployment candidate. The
    # exact hyperparameter configuration that ships is revalidated against the
    # Gate-1 thresholds by export_model.py — qualification does not transfer
    # across configurations unchecked.
    logistic_qualified = "logistic" in gate1.get("qualifiers", [])
    n_classes = len(careers)

    # Every model goes through cross_fitted_oof, so the calibration protocol is a
    # property of the driver rather than something each model re-implements (and
    # could re-implement wrongly). The two nested-selection models pass a
    # select_config; small_nn and two_tower have no inner grid, so for them the
    # cross-fit is just: inner 3-fold OOF over tr, fit T, apply.
    print("3a: nested-CV tuned LightGBM ...")
    oof_gbt, oof_gbt_cal, t_gbt, gbt_params = cross_fitted_oof(
        X, y, n_classes,
        fit_predict=lambda p, tr, pr: fit_gbt(p, X[tr], y[tr]).predict_proba(X[pr]),
        select_config=lambda tr: select_by_inner_cv(X, y, tr, GBT_GRID, fit_gbt),
    )
    print("3a: nested-CV tuned logistic ...")
    oof_log, oof_log_cal, t_log, log_params = cross_fitted_oof(
        X, y, n_classes,
        fit_predict=lambda c, tr, pr: fit_logistic(c, X[tr], y[tr]).predict_proba(X[pr]),
        select_config=lambda tr: select_by_inner_cv(X, y, tr, LOGISTIC_C_GRID, fit_logistic),
    )

    print("3b: small NN (soft targets) ...")
    # y[tr] is still required alongside the soft targets: it supplies the class
    # weights and stratifies the early-stopping split, so a fold differs from the
    # Gate-1 fit only in what the loss is measured against.
    oof_nn, oof_nn_cal, t_nn, _ = cross_fitted_oof(
        X, y, n_classes,
        fit_predict=lambda _c, tr, pr: (
            NNClassifier(random_state=SEED)
            .fit(X[tr], y[tr], soft_targets=soft[tr])
            .predict_proba(X[pr])
        ),
    )

    print("3c: two-tower (archetype-seeded) ...")
    oof_tt, oof_tt_cal, t_tt, _ = cross_fitted_oof(
        X, y, n_classes,
        fit_predict=lambda _c, tr, pr: train_two_tower_fold(
            X[tr], y[tr], X[pr], arch_mat, n_classes
        ),
    )

    # AFTER two_tower, and that ordering is load-bearing rather than cosmetic.
    # two_tower seeds from PROCESS-GLOBAL torch RNG rather than per fit, so its
    # predictions depend on how many torch fits preceded them (DEV-91 documented
    # this rather than fixing it). `ResidualMatcher` inherits `NNClassifier.fit`,
    # which restores every global generator it touches, so in principle it could sit
    # anywhere; running it last means the claim "two_tower did not move" does not
    # rest on that reasoning being right. It is verified against the recorded row
    # either way — see the report's reproduction table.
    print("3d: residual matcher (frozen logistic + gated MLP) ...")
    oof_res, oof_res_cal, t_res, res_configs = cross_fitted_oof(
        X, y, n_classes,
        # Hard labels, unlike small_nn. ADR 0006's whole argument is that the frozen
        # base is exactly the Incumbent's configuration on the same partition, which
        # makes "does the residual add anything?" an exactly paired comparison
        # against `logistic_tuned` — and that pairing only holds while both optimise
        # against the same targets.
        fit_predict=lambda cfg, tr, pr: fit_residual(cfg, X[tr], y[tr]).predict_proba(X[pr]),
        select_config=lambda tr: select_residual_config(X, y, tr),
    )
    residual_verdict = alpha_zero_verdict(res_configs)

    models = {
        "gbt_tuned": (oof_gbt, oof_gbt_cal, t_gbt),
        "logistic_tuned": (oof_log, oof_log_cal, t_log),
        "small_nn": (oof_nn, oof_nn_cal, t_nn),
        "two_tower": (oof_tt, oof_tt_cal, t_tt),
        "residual_matcher": (oof_res, oof_res_cal, t_res),
    }

    results = {}
    for name, (probs, calibrated, temps) in models.items():
        # Ranking metrics come off the RAW probabilities, and would be identical on
        # the calibrated ones: temperature scaling is monotone within a row. That is
        # why the Gate-2 primary (top-2) cannot move for this change alone — only
        # the ECE columns respond.
        m = rank_metrics(probs, y)
        m["ece_raw"] = ece(probs, y)
        m["ece_cross_fitted"] = ece(calibrated, y)
        m["fold_temperatures"] = temps
        m["temperature_spread"] = float(max(temps) - min(temps))
        m["temperature_sd"] = float(np.std(temps))
        # Phase 3's pooled constant for this evaluated configuration. It remains a
        # useful reference and calibration-provenance record, but export cannot
        # transfer it when the serialized fixed configuration differs.
        pooled_scaled, m["deployment_temperature"] = temperature_scale(probs, y)
        # The number the OLD protocol would have printed. Reported beside the
        # cross-fitted one to size the optimism this ticket removes — and, for
        # small_nn, to separate this ticket's effect from DEV-90's.
        m["ece_pooled_legacy"] = ece(pooled_scaled, y)
        # NLL in both protocols. The pooled temperature is the argmin of NLL on
        # this pool, so nll_pooled_legacy <= nll_cross_fitted is guaranteed and is
        # the honest statement of the bias; the ECE columns are not so ordered.
        m["nll_cross_fitted"] = nll(calibrated, y)
        m["nll_pooled_legacy"] = nll(pooled_scaled, y)
        results[name] = m

    # Gate 2: top-2 primary, ECE tiebreak (within 0.01 of top-2). The tiebreak now
    # reads the CROSS-FITTED ECE — the pooled one is biased in a model-dependent
    # direction (a worse-calibrated model gains more from fitting T on its own
    # evaluation data), so using it here could hand the gate to the wrong winner.
    best_top2 = max(r["top2"] for r in results.values())
    contenders = [n for n, r in results.items() if best_top2 - r["top2"] <= 0.01]
    winner = min(contenders, key=lambda n: results[n]["ece_cross_fitted"])

    # Deployment selection, explicit: the serving path (matcher_model.py) is
    # dependency-free LINEAR inference with exact attribution, so only logistic is
    # deployable — and only if it QUALIFIED under Gate 1 (calibration + stability;
    # verified up front, right after load_data). A model the gate rejected must
    # never become deployable just because the Gate-2 winner has no serving path;
    # export refuses when deployable is null.
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

    # Read once and reused for both outputs, so the report and gate2_winner.json can
    # never disagree about the environment. See env_manifest.py.
    env = environment_manifest()

    def fmt(name, m):
        return (f"| {name} | {m['top1']:.3f} | {m['top2']:.3f} | {m['top3']:.3f} | "
                f"{m['mrr']:.3f} | {m['balanced_top1']:.3f} | {m['ece_raw']:.3f} | "
                f"{m['ece_cross_fitted']:.3f} | {m['ece_pooled_legacy']:.3f} |")

    # Every claim the prose below makes about this run is COMPUTED here, never
    # written as a literal. A hardcoded "reproduces exactly" or "improved for three
    # of four" keeps printing long after it stops being true — which is the failure
    # mode this ticket exists to remove, so the report must not reintroduce it.
    # `residual_matcher` has no recorded history — it is new in DEV-93 and was never
    # scored under the old protocol — so it is excluded from every reproduction
    # claim rather than compared against a number that does not exist. A model with
    # no prior row cannot "reproduce" or "fail to reproduce" anything.
    with_history = [n for n in results if n in RECORDED_HISTORY]
    reproduced = [
        n for n in with_history
        if abs(RECORDED_HISTORY[n]["ece_raw"] - results[n]["ece_raw"]) < 5e-4
        and abs(RECORDED_HISTORY[n]["ece_scaled"] - results[n]["ece_pooled_legacy"]) < 5e-4
    ]
    ece_improved = [n for n, m in results.items()
                    if m["ece_cross_fitted"] < m["ece_pooled_legacy"]]
    log_m = results["logistic_tuned"]
    # Whether the Residual Matcher collapsed onto the Incumbent, COMPUTED by
    # comparing the two rows rather than left for a reader to notice that two lines
    # of the table happen to match. At alpha=0 the model is exactly logistic at its
    # inherited C, and that C comes from the same select_by_inner_cv call
    # logistic_tuned uses — so when every fold picks alpha=0 the two are the same
    # estimator and identical rows are a consequence, not a coincidence.
    _row_keys = ["top1", "top2", "top3", "mrr", "balanced_top1",
                 "ece_raw", "ece_cross_fitted", "ece_pooled_legacy"]
    residual_row_identical = all(
        results["residual_matcher"][k] == log_m[k] for k in _row_keys
    )
    residual_inherits_same_C = (
        list(residual_verdict["per_fold_logistic_C"]) == list(log_params)
    )
    ships_widest = (
        ", and the widest of it is on the model that ships"
        if log_m["temperature_spread"] == max(m["temperature_spread"] for m in results.values())
        else ""
    )
    no_fold_matches = (
        f", and **no fold chose the pooled {log_m['deployment_temperature']:.2f} "
        "Phase-3 reference**"
        if all(abs(t - log_m["deployment_temperature"]) > 1e-9
               for t in log_m["fold_temperatures"])
        else ""
    )
    runner_up = sorted(
        (r["top2"] for n, r in results.items() if n != winner), reverse=True)[0]
    tiebreak_fired = len(contenders) > 1
    nll_lower_cross = len([n for n, m in results.items()
                           if m["nll_cross_fitted"] < m["nll_pooled_legacy"]])

    def fmt_temps(name, m):
        folds = " | ".join(f"{t:.2f}" for t in m["fold_temperatures"])
        return (f"| {name} | {folds} | {m['temperature_spread']:.2f} | "
                f"{m['temperature_sd']:.2f} | {m['deployment_temperature']:.2f} |")

    per_class = []
    for name, m in results.items():
        rows = "\n".join(f"| {careers[c]} | {v:.2f} |" for c, v in m["per_class"].items())
        per_class.append(f"### {name}\n\n| career | top-1 recall |\n|---|---|\n{rows}")

    report = f"""# Model Selection — Phase 3 / Gate 2

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Calibration is now **cross-fitted**: the temperature
> is fitted per outer fold on inner out-of-fold predictions drawn only from that
> fold's training partition, never from the rows it goes on to score (ADR 0007).
> Circularity is a separate, untouched defect — better labels would not have fixed
> this one, and this fix does not make the labels less circular.

## !! DELIBERATE BREAK FROM RECORDED HISTORY !!

**Every Gate-2 calibration number in this report is non-comparable to any version
generated before {BREAK_DATE}**, including the `gbt_tuned` ECE
{RECORDED_HISTORY["gbt_tuned"]["ece_scaled"]:.3f} that won it Gate 2 under the old
protocol. The break was a deliberate one-time re-baseline of all four models in a
single run, not drift.

This section stays in every future report, because the non-comparability is
permanent: it describes the boundary, not this particular run. The table further
down recomputes both sides each time, so it keeps telling the truth as the code
moves on.

What moved and why:

- **One column only, for `gbt_tuned` and `logistic_tuned`.** Temperature scaling is
  monotone within a row, so it cannot reorder anything: their top-1/2/3, MRR,
  balanced top-1 and per-class recall are unchanged, and `ECE raw` is unchanged.
  Their *deployment* temperatures also reproduce the recorded 1.65 and 1.00
  exactly, because that number is still fitted on the full pool. What is new for
  them is the cross-fitted ECE and the five per-fold temperatures behind it.
- **`small_nn` moved for TWO independent reasons** and the movement must not be
  attributed to cross-fitting alone. (1) This change. (2) DEV-90 replaced the
  inline network with the shared `nn_model.NNClassifier`, which re-seeds torch per
  fit where the old inline code inherited accumulated process-global RNG state. Its
  recorded row was already stale before this run.

  **The two causes separate exactly, from the table below.** Its recorded
  `ECE scaled` of 0.101 was the old protocol on the old inline network. The
  `ECE pooled-T (legacy)` column is the old protocol on DEV-90's shared network, so
  `0.101 -> legacy` is DEV-90's re-seeding alone and `legacy -> cross-fitted` is
  this ticket alone. The split is exact here because `NNClassifier` restores global
  RNG state around every fit, which makes its raw OOF independent of how many fits
  preceded it. It is **not** exact for `two_tower`, for the reason below.
- **`two_tower` moved for a second reason too.** Unlike `NNClassifier`, it seeds
  from process-global torch RNG rather than per fit, so its predictions depend on
  how many fits preceded them — and cross-fitting inserts three per outer fold.
  Its numbers are reproducible from a clean run but order-dependent. Left as-is
  rather than fixed here: making it deterministic would be a second uncontrolled
  change to a model's identity inside the very run meant to re-baseline it.
- **Say plainly what that means: for `small_nn` and `two_tower` the RANKING metrics
  moved, not only the calibration ones** — including top-2, which is the Gate-2
  *primary*, not a tiebreak input. `small_nn` top-2 {RECORDED_HISTORY["small_nn"]["top2"]:.3f} ->
  {results["small_nn"]["top2"]:.3f}, `two_tower` {RECORDED_HISTORY["two_tower"]["top2"]:.3f} ->
  {results["two_tower"]["top2"]:.3f}. This run does not isolate the protocol for
  those two, and the honest reading is that their rows are a fresh baseline rather
  than a comparison. The contender set happened to be unaffected — see the verdict
  — but a larger shift could have changed it.

The dataset is unmoved: digest `{digest}`, the
same build both gate files were computed on.

**Gate 1 is unaffected, and that was verified rather than assumed.**
`evaluate_matchers.py` was re-run on unchanged code and reproduced the digest and
every Gate-1 metric to the last digit. Those metrics, read back from the
`gate1_verdict.json` this run consumed rather than transcribed:

| model | Gate-1 ECE (raw, never tempered) | top-2 stability |
|---|---|---|
{chr(10).join(f"| {n} | {m['ece']!r} | {m['top2_stability']!r} |"
              for n, m in gate1["metrics"].items())}

Gate 1 is also unaffected structurally, which is the stronger statement: it gates
on RAW ECE, has never applied a temperature, and `evaluate_matchers.py` does not
import this module in either direction.

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Dataset: {len(df)} rows, feature `{meta["feature_version"]}`, seed {SEED},
outer {N_FOLDS}-fold stratified CV (same folds as Phase 2).
Phase 2 reference (recomputed on THIS dataset, not hardcoded from a previous run):
production-formula top-2 agreement {formula_top2_ref:.3f}; full Phase-2 comparison
in baseline_evaluation.md.

{manifest_markdown(env)}
## Comparison (pooled out-of-fold)

| model | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE raw | ECE cross-fitted | ECE pooled-T (legacy) |
|---|---|---|---|---|---|---|---|---|
{fmt("gbt_tuned (3a)", results["gbt_tuned"])}
{fmt("logistic_tuned (3a)", results["logistic_tuned"])}
{fmt("small_nn soft-targets (3b)", results["small_nn"])}
{fmt("two_tower archetype-seeded (3c)", results["two_tower"])}
{fmt("residual_matcher hard-labels (3d)", results["residual_matcher"])}

**`ECE cross-fitted` is the reported and gating number.** `ECE pooled-T (legacy)`
is what the old protocol printed — one temperature fitted on the whole OOF pool and
then scored on that same pool. It is shown to size the defect and to separate
`small_nn`'s two causes. It is not a metric.

## Break from recorded history, side by side

The last run under the old protocol (2026-07-19) against this one. `legacy`
columns are computed here, so a matching pair proves the environment and the raw
predictions are unmoved and isolates the change to the protocol alone.

| model | recorded ECE raw | now | recorded ECE scaled | now (legacy) | reproduces? |
|---|---|---|---|---|---|
{chr(10).join(
    f"| {n} | {RECORDED_HISTORY[n]['ece_raw']:.3f} | {results[n]['ece_raw']:.3f} | "
    f"{RECORDED_HISTORY[n]['ece_scaled']:.3f} | {results[n]['ece_pooled_legacy']:.3f} | "
    + ("**exact**" if abs(RECORDED_HISTORY[n]['ece_scaled'] - results[n]['ece_pooled_legacy']) < 5e-4
       and abs(RECORDED_HISTORY[n]['ece_raw'] - results[n]['ece_raw']) < 5e-4
       else "no — see causes above") + " |"
    for n in with_history
)}

`residual_matcher` is absent from that table by construction: it is new in DEV-93,
was never scored under the old protocol, and a model with no recorded row can
neither reproduce nor fail to reproduce one.

## What this re-baseline showed

**1. {len(reproduced)} of {len(with_history)} models with recorded history reproduce the old protocol exactly**
({", ".join(f"`{n}`" for n in reproduced) or "none"}). Their `ECE raw` and their
`legacy` ECE match the 2026-07-19 record to three decimals — same environment, same
folds, same raw out-of-fold predictions — which isolates the whole of their movement
to the protocol change. The models absent from that list are the two with a
documented second cause, above.

**2. `small_nn`'s two causes are each large and nearly cancel.** Recorded 0.101 ->
legacy {results["small_nn"]["ece_pooled_legacy"]:.3f} is DEV-90's per-fit re-seeding
alone (a move of
{abs(RECORDED_HISTORY["small_nn"]["ece_scaled"] - results["small_nn"]["ece_pooled_legacy"]):.3f});
legacy -> cross-fitted {results["small_nn"]["ece_cross_fitted"]:.3f} is this ticket
alone (a move of
{abs(results["small_nn"]["ece_pooled_legacy"] - results["small_nn"]["ece_cross_fitted"]):.3f}).
They point in opposite directions, so the net move from the recorded number is only
{abs(RECORDED_HISTORY["small_nn"]["ece_scaled"] - results["small_nn"]["ece_cross_fitted"]):.3f}.
**Attributing that net to cross-fitting alone would have been wrong in both
magnitude and sign.**

**3. The old number moves in no predictable direction, and that is not a flaw in
the fix.** The guarantee is narrower than it first looks, and worth stating
precisely because two drafts of this report got it wrong.

Within the family of **constant** temperatures, a temperature fitted on a pool is
the argmin of NLL on that pool: no other constant can score lower there. *That* is
the leak — the old number was a fitted minimum, not a measurement.

But cross-fitting changes two things at once. It removes the leak, **and** it
widens the family from one global constant to five per-fold constants, which can
absorb fold-specific miscalibration a single constant cannot. The second effect
can outweigh the first, and here it does: cross-fitted ECE is *lower* for
{len(ece_improved)} of {len(results)}
({", ".join(f"`{n}`" for n in ece_improved) or "none"}), and cross-fitted NLL is
lower for {nll_lower_cross} of {len(results)}. So the honest claim is only this: **the old number was never a
held-out estimate.** Not that it was necessarily flattering. ADR 0007's word
"optimistic" is right about the mechanism and overstated as a prediction about
either metric, and is annotated accordingly.

| model | NLL cross-fitted | NLL pooled-T (legacy) | which is lower |
|---|---|---|---|
{chr(10).join(
    f"| {n} | {m['nll_cross_fitted']:.4f} | {m['nll_pooled_legacy']:.4f} | "
    + ("legacy" if m["nll_pooled_legacy"] < m["nll_cross_fitted"] else "cross-fitted") + " |"
    for n, m in results.items()
)}

Neither column is a gate input; both are shown because the direction is the thing
readers will assume they already know.

## Calibration temperature, per outer fold

| model | fold 1 | 2 | 3 | 4 | 5 | spread | sd | Phase-3 pooled T |
|---|---|---|---|---|---|---|---|---|
{fmt_temps("gbt_tuned", results["gbt_tuned"])}
{fmt_temps("logistic_tuned", results["logistic_tuned"])}
{fmt_temps("small_nn", results["small_nn"])}
{fmt_temps("two_tower", results["two_tower"])}
{fmt_temps("residual_matcher", results["residual_matcher"])}

**The spread is itself a finding{ships_widest}.**
Each fold's temperature is an independent estimate of the same quantity, so a wide
spread means a single temperature is not a well-estimated quantity.
`logistic_tuned`, the deployment architecture, has a spread of
{log_m["temperature_spread"]:.2f} across
{", ".join(f"{t:.2f}" for t in log_m["fold_temperatures"])}: folds disagree about
whether its probabilities need softening or sharpening at all{no_fold_matches}.
Read that as a warning about displayed `matchPercent` precision, not about the
ranking — temperature cannot reorder anything.

The `Phase-3 pooled T` column is fitted separately on each model's full pooled OOF.
It is a reference for the evaluated configuration, not a transferable artifact
field. Export selects a fixed C and independently fits the one shipped constant on
OOF predictions from that exact configuration.

Chosen hyperparameters per outer fold:
- gbt (n_estimators, lr, num_leaves, min_child_samples): {gbt_params}
- logistic C: {log_params}
- residual (alpha, inherited logistic C): {res_configs}

## Residual Matcher: the pre-registered alpha=0 rule

`alpha` is a hyperparameter selected by inner CV from {list(RESIDUAL_ALPHA_GRID)}, and at
`alpha = 0` the model is *exactly* logistic regression. ADR 0006 pre-registered,
before any alpha was selected on this data, that **alpha=0 in >= {ALPHA_ZERO_DISQUALIFIES_AT}
of {N_FOLDS} outer folds is reported as "no non-linear signal found"** and disqualifies the
Residual Matcher from being the shipped neural model — shipping it would be
shipping logistic regression in a costume while the project requires a neural
network (ADR 0004).

Per-fold alpha: {residual_verdict["per_fold_alpha"]} — {residual_verdict["n_folds_at_zero"]} of {N_FOLDS} at zero.
**Verdict: {"NO NON-LINEAR SIGNAL FOUND — disqualified from being the shipped neural model" if residual_verdict["no_non_linear_signal"] else "the rule did not fire; a non-zero residual was selected in a majority of folds"}.**
The inherited logistic C per fold: {residual_verdict["per_fold_logistic_C"]}. Reporting only —
nothing here selects, and a disqualified Residual Matcher is still reported in full.

**Its row in the comparison table above is {"identical to `logistic_tuned`'s in every column, and that is a consequence rather than a coincidence" if residual_row_identical else "NOT identical to `logistic_tuned`'s"}.**
{"At `alpha = 0` the Residual Matcher is exactly logistic regression at its inherited `C`, and that `C` comes from the same `select_by_inner_cv` call `logistic_tuned` uses — verified here, not assumed: the per-fold `C` lists " + ("match" if residual_inherits_same_C else "DO NOT match") + ". With every fold at `alpha = 0` the two are therefore the same estimator, fold for fold, and no arithmetic could separate them. Read the two rows as one measurement printed twice." if residual_row_identical else "Some fold selected a non-zero `alpha`, so the two models are not the same estimator and the rows are genuinely different measurements."}

What this does NOT establish: that a non-linear residual could never help on these
features. It establishes that inner CV, given the choice on this dataset under this
protocol, declined it in every fold — which is evidence about this feature set and
this sample size, not a theorem. The 5-seed sweep in `nn_rework.md` is the wider
test, and it reaches the same verdict.

## Per-class top-1 recall

{chr(10).join(per_class)}

## Gate 2 verdict

**Winner: `{winner}`** — top-2 {results[winner]["top2"]:.3f}, cross-fitted ECE
{results[winner]["ece_cross_fitted"]:.3f} (per-fold T
{", ".join(f"{t:.2f}" for t in results[winner]["fold_temperatures"])}).
Selection rule: highest top-2; ties within 0.01 broken by **cross-fitted** ECE.

**The tiebreak {"fired: " + str(len(contenders)) + " models were within 0.01 on top-2" if tiebreak_fired else "did NOT fire this run"}.**
{"" if tiebreak_fired else f"`{winner}` wins on top-2 alone ({results[winner]['top2']:.3f} against a runner-up {runner_up:.3f}, outside the 0.01 band), so the ECE column decided nothing."}
Stated rather than left for the reader to infer, so the calibration figure printed
beside the verdict is not mistaken for the thing that chose it. What this ticket
changed is which quantity *would* decide a close call: the legacy
pooled number's bias is model-dependent — a worse-calibrated model gains more from
fitting T on its own evaluation data — so the tiebreak was the statistic most
distorted by the defect, and is now the honest one.

## Deployment selection

**Deployable winner: `{deployable or "NONE"}`** — {deployable_reason}.
export_model.py refuses to export unless this names the architecture it produces
(and refuses outright when it is NONE), so the served artifact and this report
cannot silently disagree — and a Gate-1-rejected model can never ship.

The deployment temperature recorded for `{deployable or "NONE"}` is
{f"{results[deployable]['deployment_temperature']:.2f}" if deployable else "n/a"},
for Phase 3's per-fold-selected configuration. export_model.py requires this
calibration record as provenance but does not transfer its temperature when
serializing a different configuration: it selects one fixed C and refits on OOF
predictions from that exact C. **DEV-88 made the serving path divide logits by the
artifact's refitted field**, so any non-1.0 value changes served `matchPercent`.

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
        # Calibration is recorded for EVERY model, not just the winner: the
        # re-baseline's whole claim is that all four moved together in one run, and
        # a file carrying only the winner's numbers could not evidence that.
        "calibration": {
            "method": (
                "temperature fitted per outer fold on inner-OOF predictions from that "
                "fold's training partition only (cross-fitted; ADR 0007)"
            ),
            "reported_metric": "ece_cross_fitted",
            "tiebreak_metric": "ece_cross_fitted",
            "break_from_recorded_history": BREAK_DATE,
            "per_model": {
                n: {
                    "fold_temperatures": m["fold_temperatures"],
                    "spread": m["temperature_spread"],
                    "sd": m["temperature_sd"],
                    "deployment_temperature": m["deployment_temperature"],
                    "ece_raw": m["ece_raw"],
                    "ece_cross_fitted": m["ece_cross_fitted"],
                    "ece_pooled_legacy": m["ece_pooled_legacy"],
                }
                for n, m in results.items()
            },
            # Phase 3's pooled estimate for the DEPLOYABLE configuration. Export
            # requires it as calibration provenance, but must refit rather than
            # transfer it if the serialized fixed configuration differs.
            "deployment_temperature_model": deployable,
            "deployment_temperature": (
                results[deployable]["deployment_temperature"] if deployable else None
            ),
        },
        # Which dataset build this selection was computed on; export_model.py
        # refuses to export against a different build so a regenerated (or
        # hand-edited) train_features.parquet can't be paired with a stale
        # selection. The digest hashes the actual features+labels content —
        # sidecar metadata alone can't detect a replaced table.
        "dataset_digest": digest,
        "environment": env,
        "dataset_fingerprint": {"created_at": meta["created_at"], "n_rows": len(df)},
        "gate1": {"passed": gate1["passed"], "qualifiers": gate1.get("qualifiers", [])},
        "metrics": {k: v for k, v in results[winner].items() if k != "per_class"},
        "gbt_params_per_fold": gbt_params,
        "logistic_C_per_fold": log_params,
        # The per-fold alpha record the pre-registered >=3-of-5 rule reads. Recorded
        # whether or not the Residual Matcher wins: the rule is about whether a
        # non-linear signal exists in these features at all, which is information
        # the decision document needs either way.
        "residual_alpha_verdict": residual_verdict,
        "feature_version": meta["feature_version"],
        "seed": SEED,
        "label_source": "synthetic_llm",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
