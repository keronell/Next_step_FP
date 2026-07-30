"""Round 1 of the DEV-23 neural-matcher rework: the nested 14-Variant sweep.

Plan: `docs/dev-23-nn-rework-plan.md` Steps 2.2, 2.4, 2.5, 2.7. Vocabulary is
`CONTEXT.md`'s — Variant, Ship Floor, Incumbent, Qualified/Selected/Servable/
Deployable are defined terms and are not used loosely here.

Run from repo root, in the hash-pinned training venv (`data/scripts/README.md`;
`Scripts/` rather than `bin/` on Windows):

    data/venv-training/Scripts/python data/scripts/sweep_variants.py

Output: `data/training/nn_rework.md`, `data/training/round1_results.json`.

**The run checkpoints per experiment seed** to `round1_checkpoint.json`. The full
sweep is hours and this environment kills long jobs around the 5-hour mark, so it
must be able to resume rather than restart; re-running after all seeds are complete
regenerates the report from the checkpoint without refitting anything, which is also
how the report gets edited without paying for the sweep twice. The checkpoint is
keyed on the dataset digest and is discarded rather than merged if that moves.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from nn_model import NNClassifier, ResidualMatcher, SeedEnsemble, frozen_logistic

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAINING_DIR = REPO_ROOT / "data" / "training"
OUT_MD = TRAINING_DIR / "nn_rework.md"
OUT_JSON = TRAINING_DIR / "round1_results.json"
CHECKPOINT = TRAINING_DIR / "round1_checkpoint.json"

SEED = 42
N_BOOTSTRAP = 10_000
# Each experiment seed is a COMPLETE nested run, varying both the fold partition and
# the initialisation. Seeds sit outside selection: inner CV runs single-seed.
EXPERIMENT_SEEDS = (42, 43, 44, 45, 46)
# Step 2.5's materiality marker, not a gate. Under a hard requirement (ADR 0001)
# nothing authorises a decision; this sizes the gap.
MATERIALITY_DELTA = 0.02

# Full-batch as an ARGUMENT rather than a code path: `torch.randperm(n).split(k)`
# with k larger than any training partition yields exactly one batch. Keeping it an
# argument is what lets the sweep vary configurations without editing nn_model.py.
FULL_BATCH = 10**9


# ------------------------------------------------------------- the 14 Variants
@dataclass(frozen=True)
class Variant:
    """One fully-specified Learned Matcher configuration entered into the sweep.

    `CONTEXT.md`'s term, and distinct from a hyperparameter setting explored inside
    a fold: all 14 of these are fixed before any data is seen, which is what lets
    Step 2.4 delete the pruning pass.
    """

    name: str
    axis: str  # capacity | regularization | protocol
    kind: str  # mlp | ensemble | residual
    rationale: str
    kwargs: dict = field(default_factory=dict)


CONTROL = "V0_control"


def _variants() -> dict[str, Variant]:
    specs = [
        # --- Axis A: capacity (4). Hypothesis: the current net is too large for 232 rows.
        Variant("A1_84_16_16", "capacity", "mlp",
                "one hidden layer of 16 -- the smallest net that still has a hidden layer",
                {"hidden_sizes": (16,)}),
        Variant("A2_84_32_16", "capacity", "mlp",
                "one hidden layer of 32",
                {"hidden_sizes": (32,)}),
        Variant("A3_84_64_16", "capacity", "mlp",
                "one hidden layer of 64 -- V0's width without V0's depth",
                {"hidden_sizes": (64,)}),
        Variant(CONTROL, "capacity", "mlp",
                "V0: the configuration small_nn's recorded Gate-1 and Gate-2 numbers "
                "came from, entered as the control (plan Step 2.2, A4)",
                {}),
        # --- Axis B: regularization (5), each applied on top of V0.
        Variant("B1_dropout_0.1", "regularization", "mlp",
                "less dropout than V0's 0.3", {"dropout": 0.1}),
        Variant("B2_dropout_0.5", "regularization", "mlp",
                "more dropout than V0's 0.3", {"dropout": 0.5}),
        Variant("B3_wd_1e-3", "regularization", "mlp",
                "10x V0's weight decay", {"weight_decay": 1e-3}),
        Variant("B4_wd_1e-2", "regularization", "mlp",
                "100x V0's weight decay", {"weight_decay": 1e-2}),
        Variant("B5_input_noise_0.1", "regularization", "mlp",
                "Gaussian input noise sigma=0.1 on standardized features, training only",
                {"input_noise": 0.1}),
        # --- Axis C: protocol (5).
        Variant("C0_batch_16", "protocol", "mlp",
                "half V0's batch size -- more gradient steps per epoch at n=232",
                {"batch_size": 16}),
        Variant("C1_full_batch", "protocol", "mlp",
                "one gradient step per epoch; no minibatch noise at all",
                {"batch_size": FULL_BATCH}),
        Variant("C2_sgd_cosine", "protocol", "mlp",
                "SGD+momentum 0.9 with a cosine learning-rate schedule instead of Adam",
                {"optimizer": "sgd", "lr_schedule": "cosine"}),
        Variant("C3_seed_ensemble", "protocol", "ensemble",
                "5 members differing only in seed, averaged in probability; a separate "
                "Variant, never fused into the Residual Matcher",
                {}),
        Variant("C4_residual_matcher", "protocol", "residual",
                "frozen logistic branch plus a gated MLP correction; alpha selected by "
                "inner CV, C inherited from the fold's tuned-logistic selection (ADR 0003)",
                {}),
    ]
    return {v.name: v for v in specs}


VARIANTS = _variants()


def build_variant(variant: Variant, random_state: int, config=None):
    """Construct the estimator for `variant`, unfitted.

    `config` is the per-outer-fold `(alpha, C)` for the Residual Matcher — resolved
    by `train_models.select_residual_config` on the outer fold's TRAINING partition
    only — and is ignored by every other kind. It is a required argument for the
    residual rather than a default, because a silently-defaulted alpha would make
    the pre-registered >=3-of-5 zero rule read a number nobody chose.
    """
    if variant.kind == "residual":
        if config is None:
            raise ValueError(
                f"{variant.name} needs its per-fold (alpha, C) from "
                "train_models.select_residual_config — alpha is selected by inner CV, "
                "not defaulted (ADR 0003)"
            )
        alpha, C = config
        return ResidualMatcher(
            random_state=random_state, alpha=alpha, logistic_C=C, **variant.kwargs
        )
    if variant.kind == "ensemble":
        return SeedEnsemble(random_state=random_state, **variant.kwargs)
    return NNClassifier(random_state=random_state, **variant.kwargs)


# ------------------------------------------------- the 14-way contest (2.4)
def select_variant(X, y, tr, random_state: int, variants=None, scores_out=None):
    """Pick the Variant with the best inner-CV top-2, using ONLY `tr`.

    This is `train_models.select_by_inner_cv` — the same grid-argmax every other
    nested selection in this pipeline goes through, with the 14 Variants as the
    grid — rather than a second implementation. That is the point of Step 2.4: there
    is no separate selection stage to leak, because Variant selection *is* the inner
    CV that was already there.

    The Residual Matcher's `(alpha, C)` is resolved first, on `tr` alone, because
    ADR 0003 pre-registered alpha as an inner-CV-selected hyperparameter.

    **That resolution runs on the same inner splits that then rank all 14** — same
    `tr`, same `random_state`, so the same `StratifiedKFold`. The Residual Matcher
    therefore enters the contest with a score that is a MAXIMUM over its alpha grid,
    evaluated on the ranking metric itself, while every pure-MLP Variant contributes
    a single configuration's score. A maximum over several draws beats a single draw
    on average even when nothing differs between them, so its inner-CV score is
    **optimistically biased relative to its competitors** and the selection counts
    must be read with that in mind. This is NOT Leakage in `CONTEXT.md`'s sense — no
    held-out row is touched, and `test_variant_selection.py` pins that — it is
    selection optimism inside the training partition. Left in place because removing
    it means selecting alpha at a third nesting level, which ADR 0003 considered and
    declined; reported in full in `nn_rework.md` rather than described as merely
    "one extra search".

    Returns `(variant_name, residual_configs)`, where `residual_configs` maps every
    residual Variant to the `(alpha, C)` inner CV chose for it **on this fold,
    whether or not it went on to win the contest**. Returning only the winner's
    config would leave the pre-registered >=3-of-5 alpha rule reading a record with
    holes in it — "this fold did not pick the Residual Matcher" is not the same
    finding as "this fold picked alpha=0", and conflating them would let the rule
    fire, or fail to fire, on the wrong evidence.

    `scores_out` is an optional dict that receives `{variant_name: inner-CV top-2}`
    for **all** of them, winner and losers alike (DEV-95). Round 1 kept only the
    argmax, and when ADR 0003's rule disqualified the winner its own output could not
    name the replacement the rule owes — the ranking among the Variants that were
    never selected had been computed 25 times and discarded each time. It is an
    out-parameter for the reason `train_models.select_by_inner_cv` documents: the
    return value has existing callers and a test asserting on it directly.

    A pure function of `tr` — held by `test_variant_selection.py`, which poisons
    every row outside `tr` and requires the answer not to move.

    **Ties are broken by registry order, and that is not neutral.**
    `select_by_inner_cv` keeps the first strictly-better score, so when two Variants
    tie on inner-CV top-2 the one declared earlier in `_variants()` wins. At n=232
    with roughly 62 rows per inner-validation split, exact ties are common rather
    than exotic. The registry declares the capacity axis first, so ties resolve
    toward the **lower-capacity** Variants. That is a defensible default under this
    plan's own hypothesis — that the current net is too large for 232 rows — but it
    is a thumb on the scale, it was fixed before the data was seen, and the record
    cannot distinguish a tie-broken pick from a decisive one. Reported, not hidden.

    **The whole sweep trains on HARD labels**, here and when the selected Variant is
    refit. Two reasons, and one consequence that must not be lost. Selection on hard
    labels is what every other nested selection in this pipeline does, and Round 1
    asks whether architecture, regularization or protocol helps — entering a
    soft-target objective as well would confound that question with a 15th axis
    present in no Variant's specification. The comparators `gbt_tuned` and
    `logistic_tuned` are hard-label models too, so the paired comparison is
    like-for-like. **The consequence:** the control Variant is the *Gate-1*
    `small_nn` configuration, not the Gate-2 `small_nn` row, which additionally
    consumes the panel vote distribution. The report says so; the two numbers are
    not a series.
    """
    import train_models  # local: train_models must not import this module back

    variants = VARIANTS if variants is None else variants
    residual_config = {
        name: train_models.select_residual_config(X, y, tr, random_state=random_state)
        for name, variant in variants.items() if variant.kind == "residual"
    }

    scored: list = []
    chosen = train_models.select_by_inner_cv(
        X, y, tr, list(variants),
        lambda name, Xtr, ytr: build_variant(
            variants[name], random_state=random_state, config=residual_config.get(name)
        ).fit(Xtr, ytr),
        random_state=random_state,
        scores_out=scored,
    )
    if scores_out is not None:
        scores_out.update(scored)
    return chosen, residual_config


# ------------------------------------------------------- paired bootstrap (2.4)
def paired_bootstrap(
    profile_ids,
    hits_a,
    hits_b,
    n_resamples: int = N_BOOTSTRAP,
    random_state: int = SEED,
    ci: float = 0.95,
) -> dict:
    """Paired bootstrap CI for `mean(a) - mean(b)`, resampling PROFILES.

    The three inputs are parallel arrays over profile-seed rows — one row per
    (profile, experiment seed) — because that is the shape the sweep produces. They
    are NOT the sampling unit. Each profile's indicators are averaged across its
    seeds first, and the resample then draws profile ids with replacement, so a
    profile enters a resample with all of its seeds or with none of them.

    Treating the 1,160 profile-seed rows as independent would understate the
    standard error by about sqrt(5) = 2.2x and narrow every interval in the
    deliverable without leaving a trace in the output.

    What the interval covers, and the report must say so: profile sampling
    variability CONDITIONAL on the seeds drawn. It does not fold in seed
    variability — a two-way bootstrap over 5 seeds would be hopelessly underpowered
    on the seed dimension — so per-seed results are reported as a separate table.
    """
    profile_ids = np.asarray(profile_ids)
    hits_a = np.asarray(hits_a, dtype=float)
    hits_b = np.asarray(hits_b, dtype=float)

    units, inverse = np.unique(profile_ids, return_inverse=True)
    counts = np.bincount(inverse, minlength=len(units))
    # Average inside the unit, before differencing. Order matters only for
    # readability here (both are linear), but it is the order the plan specifies
    # and the one a reader checks.
    mean_a = np.bincount(inverse, weights=hits_a, minlength=len(units)) / counts
    mean_b = np.bincount(inverse, weights=hits_b, minlength=len(units)) / counts
    per_profile_diff = mean_a - mean_b

    rng = np.random.default_rng(random_state)
    draws = rng.integers(0, len(units), size=(n_resamples, len(units)))
    resampled = per_profile_diff[draws].mean(axis=1)

    lo, hi = (1 - ci) / 2 * 100, (1 + ci) / 2 * 100
    return {
        "delta": float(per_profile_diff.mean()),
        "ci_low": float(np.percentile(resampled, lo)),
        "ci_high": float(np.percentile(resampled, hi)),
        "ci_level": ci,
        "n_profiles": int(len(units)),
        "n_rows": int(len(profile_ids)),
        "n_resamples": int(n_resamples),
        "sampling_unit": "profile",
    }


# ------------------------------------------------------------- one nested run
def fold_record(winner: str, scores: dict, residual_config: dict) -> dict:
    """One outer fold's contest result: who won, and what every Variant scored.

    One builder because there are two producers — this module's `sweep_leg` and
    `sweep_round2.scoreboard_one_seed` — and two consumers that read the result by key
    (`sweep_round2.rank_variants` and `tie_break_incidence`). Two hand-built copies of
    the same shape is how a producer quietly stops emitting `scores` and a consumer
    starts ranking a subset of the contests.
    """
    return {
        "winner": winner,
        "scores": {name: float(s) for name, s in scores.items()},
        "residual_config": {n: list(c) for n, c in residual_config.items()},
    }


def sweep_leg(X, y, n_classes, experiment_seed: int, variants=None,
              scoreboard_out=None) -> dict:
    """The contest leg of one nested run: select a Variant per outer fold, refit it,
    and score the pooled OOF — for whichever registry is passed.

    Extracted from `run_one_seed` by DEV-95 so Round 2 can run the identical protocol
    over a different Variant set without a second copy of this wiring. `variants`
    defaults to Round 1's fourteen, so `run_one_seed` is unchanged by the extraction.

    Every model goes through `train_models.cross_fitted_oof`, so the calibration
    protocol stays a property of that driver rather than something this file
    re-implements (and could re-implement wrongly). Variant selection is its
    `select_config` argument, exactly where the plan puts it.

    `scoreboard_out` optionally collects the full per-Variant inner-CV score vector
    for each outer fold (DEV-95), the evidence Round 1 discarded.
    """
    import train_models as tm

    variants = VARIANTS if variants is None else variants
    per_fold_variants: list[str] = []
    per_fold_residual: list = []

    def select_sweep_variant(tr):
        scores: dict = {}
        name, residual_configs = select_variant(
            X, y, tr, random_state=experiment_seed, variants=variants, scores_out=scores,
        )
        per_fold_variants.append(name)
        # Recorded for EVERY fold, not only the folds the residual won — see
        # select_variant on why the >=3-of-5 rule needs a record without holes.
        per_fold_residual.append(residual_configs)
        if scoreboard_out is not None:
            scoreboard_out.append(fold_record(name, scores, residual_configs))
        return (name, residual_configs.get(name))

    def fit_sweep(config, tr, pr):
        name, residual_config = config
        return build_variant(
            variants[name], random_state=experiment_seed, config=residual_config
        ).fit(X[tr], y[tr]).predict_proba(X[pr])

    print(f"  seed {experiment_seed}: nested {len(variants)}-Variant sweep ...", flush=True)
    oof, oof_cal, temps, _ = tm.cross_fitted_oof(
        X, y, n_classes, fit_predict=fit_sweep, select_config=select_sweep_variant,
        random_state=experiment_seed,
    )
    leg = _summarize(oof, oof_cal, temps, y)
    leg["per_fold_variant"] = per_fold_variants
    # {residual variant name: [(alpha, C) per outer fold]} — complete, so the
    # pre-registered rule reads what inner CV actually chose in all 5 folds. Empty
    # when the registry holds no residual Variant, which is Round 2's case: ADR 0003
    # disqualified it, so it no longer competes for a place that it may not take.
    leg["per_fold_residual_config"] = {
        name: [list(fold[name]) for fold in per_fold_residual]
        for name in per_fold_residual[0]
    }
    return leg


def comparator_legs(X, y, n_classes, experiment_seed: int) -> dict:
    """The two Gate-2 comparators under this seed's nested protocol.

    Extracted from `run_one_seed` by DEV-95 for the same reason `sweep_leg` was: Round
    2 needs to be able to recompute exactly these numbers — to verify the ones it
    reuses from Round 1's checkpoint — and a second copy of this wiring could differ
    from the one that produced them without anything failing.

    Nothing here depends on the Variant registry, which is why reuse across rounds is
    sound at all: within a seed the fold partition is a function of the seed alone.
    """
    import train_models as tm

    out = {}
    print(f"  seed {experiment_seed}: nested-CV tuned logistic ...", flush=True)
    oof, oof_cal, temps, log_cs = tm.cross_fitted_oof(
        X, y, n_classes,
        fit_predict=lambda c, tr, pr: tm.fit_logistic(c, X[tr], y[tr]).predict_proba(X[pr]),
        select_config=lambda tr: tm.select_by_inner_cv(
            X, y, tr, tm.LOGISTIC_C_GRID, tm.fit_logistic, random_state=experiment_seed
        ),
        random_state=experiment_seed,
    )
    out["logistic_tuned"] = _summarize(oof, oof_cal, temps, y)
    out["logistic_tuned"]["per_fold_config"] = list(log_cs)

    print(f"  seed {experiment_seed}: nested-CV tuned LightGBM ...", flush=True)
    oof, oof_cal, temps, gbt_ps = tm.cross_fitted_oof(
        X, y, n_classes,
        fit_predict=lambda p, tr, pr: tm.fit_gbt(p, X[tr], y[tr]).predict_proba(X[pr]),
        select_config=lambda tr: tm.select_by_inner_cv(
            X, y, tr, tm.GBT_GRID, tm.fit_gbt, random_state=experiment_seed
        ),
        random_state=experiment_seed,
    )
    out["gbt_tuned"] = _summarize(oof, oof_cal, temps, y)
    out["gbt_tuned"]["per_fold_config"] = [list(p) for p in gbt_ps]

    return out


def run_one_seed(X, y, n_classes, experiment_seed: int) -> dict:
    """One complete nested run: the sweep's NN, plus the two Gate-2 comparators,
    all on the SAME outer folds.

    Sharing folds within a seed is what makes the comparison paired — the bootstrap
    differences per-profile indicators, which means nothing if the models were
    scored on different partitions.
    """
    return {
        "sweep_nn": sweep_leg(X, y, n_classes, experiment_seed),
        **comparator_legs(X, y, n_classes, experiment_seed),
    }


def _summarize(oof, oof_calibrated, temperatures, y) -> dict:
    """Pooled metrics plus the PER-PROFILE top-2 hit indicator.

    The per-row indicator is the thing the paired bootstrap consumes, so it is
    carried out of every run rather than recomputed from a pooled number that has
    already thrown away which profile was which.
    """
    import train_models as tm

    order = np.argsort(-oof, axis=1)[:, :2]
    top2_hit = np.array([float(y[i] in order[i]) for i in range(len(y))])
    return {
        "top2": float(top2_hit.mean()),
        "top1": float((oof.argmax(axis=1) == y).mean()),
        "ece_cross_fitted": tm.ece(oof_calibrated, y),
        "ece_raw": tm.ece(oof, y),
        "fold_temperatures": [float(t) for t in temperatures],
        "top2_hit": top2_hit.tolist(),
    }


# --------------------------------------------------------------- checkpointing
def _load_checkpoint(digest: str) -> dict:
    """Resume a partial run, or start clean if the dataset moved.

    A single seed is 15-25 minutes and the whole sweep is hours; this environment
    kills long jobs around the 5-hour mark, so a run must be able to resume rather
    than restart. The unit is one experiment seed, because that is the largest piece
    whose loss is cheap and the smallest piece that is independently meaningful.

    Keyed on the dataset digest: a checkpoint written against a different build of
    `train_features.parquet` is silently wrong rather than obviously wrong, so it is
    discarded instead of merged.
    """
    if not CHECKPOINT.exists():
        return {"dataset_digest": digest, "seeds": {}}
    saved = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if saved.get("dataset_digest") != digest:
        print("checkpoint was written against a different dataset build - discarding")
        return {"dataset_digest": digest, "seeds": {}}
    if saved.get("seeds"):
        print(f"resuming: seeds {sorted(saved['seeds'])} already complete")
    return saved


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT.write_text(json.dumps(state), encoding="utf-8")


# ------------------------------------------------------------- ship floor (2.7)
def evaluate_ship_floor(X, y, n_classes, variant: Variant, config, random_state: int) -> dict:
    """Score ONE exact configuration against the Ship Floor of ADR 0002.

    Qualified is a property of one exact configuration and is never inherited by a
    reconfigured model (`CONTEXT.md`), so this is deliberately not run on "the
    winning architecture": it is run on the single configuration the sweep most
    often selected, named in the result.

    **The stability floor may not be evaluated until the determinism assertion
    passes**, and that ordering is enforced here rather than remembered: an
    estimator whose refits on identical data disagree would have its own randomness
    read as training-subset variation, and the hard floor could fire on a
    measurement artifact. `assert_deterministic` raises `SystemExit` rather than
    returning a flag, so there is no path where a stability number is produced
    without it.

    Returns both halves separately because they are not equally negotiable: top-2
    stability >= 0.60 is hard and unmitigable; ECE <= 0.10 is mitigable — a model
    failing it may still ship as the *ranking* source with displayed percentages
    falling back to the formula's.
    """
    import evaluate_matchers as em

    def factory():
        return build_variant(variant, random_state=random_state, config=config)

    em.assert_deterministic(variant.name, factory, X, y)
    # One seed drives BOTH the estimator's initialisation and the fold partition,
    # the same coupling the sweep's experiment seed uses -- so re-measuring under
    # another seed varies the two things together rather than isolating one.
    oof, stability = em.cv_oof_and_stability(
        X, y, factory, n_classes, random_state=random_state
    )
    ece = em.rank_metrics(oof, y, oof, n_classes)["ece"]
    return {
        "configuration": variant.name,
        "residual_config": list(config) if config is not None else None,
        "random_state": random_state,
        "determinism_assertion": "passed",
        "ece": float(ece),
        "ece_floor": em.GATE1_MAX_ECE,
        "ece_clears": bool(ece <= em.GATE1_MAX_ECE),
        "top2_stability": float(stability),
        "stability_floor": em.GATE1_MIN_TOP2_STABILITY,
        "stability_clears": bool(stability >= em.GATE1_MIN_TOP2_STABILITY),
    }


def ship_floor_across_seeds(X, y, n_classes, variant: Variant, config, seeds) -> dict:
    """The Ship Floor halves re-measured under each experiment seed.

    Reported beside the gated single-seed verdict, never replacing it: Gate 1's
    convention is one fixed partition, and quietly switching the gated number to a
    5-seed mean would be moving a threshold after seeing the data.

    It exists because the stability floor is **hard and unmitigable** (ADR 0002) --
    failing it escalates as a project-level finding rather than degrading -- while
    every other number in this deliverable is a 5-seed measurement. A hard threshold
    resting on one draw of the fold partition, in a ticket whose premise is that
    nobody had run seed variance on these numbers, is exactly the gap this closes.
    """
    out = {}
    for s in seeds:
        floor = evaluate_ship_floor(X, y, n_classes, variant, config, int(s))
        out[str(s)] = {
            "top2_stability": floor["top2_stability"],
            "ece": floor["ece"],
            "stability_clears": floor["stability_clears"],
            "ece_clears": floor["ece_clears"],
        }
    stabilities = [v["top2_stability"] for v in out.values()]
    eces = [v["ece"] for v in out.values()]
    return {
        "per_seed": out,
        "stability_mean": float(np.mean(stabilities)),
        "stability_sd": float(np.std(stabilities)),
        "stability_min": float(min(stabilities)),
        "seeds_clearing_stability": sum(1 for v in out.values() if v["stability_clears"]),
        "ece_mean": float(np.mean(eces)),
        "ece_sd": float(np.std(eces)),
        "ece_max": float(max(eces)),
        "seeds_clearing_ece": sum(1 for v in out.values() if v["ece_clears"]),
        "n_seeds": len(out),
    }


# -------------------------------------------------------------------- report
# The report text is COMPUTED from the run, never written as a literal. DEV-91
# asserted "the pooled temperature is optimistic" twice and the real data falsified
# both; it was caught only because the surrounding claims were computed, so the
# report printed a failure next to its own paragraph. That property is kept here.
#
# ASCII only in everything that reaches the REPORT or the console -- this template,
# the `Variant.rationale` strings it interpolates, and any print(). Docstrings and
# comments below are exempt; they never reach either.
#
# The rule is stricter than the failure it prevents, deliberately. Reports are
# written UTF-8 but printed to a cp1252 console, and a character outside that
# codepage raises on the final print with exit 1 AFTER the files are on disk -- a
# failure that looks like the run failed when it did not. cp1252 does cover the
# dashes and quotes an editor inserts by habit, so most slips would survive; ASCII
# is the version of the rule that can be checked at a glance rather than by
# remembering a codepage.
def _gate1_metrics() -> dict:
    """Gate-1 numbers read back from the verdict file this tree carries, so the
    report cannot quote a stale transcription of them."""
    return json.loads(
        (TRAINING_DIR / "gate1_verdict.json").read_text(encoding="utf-8")
    )["metrics"]


def _report(r: dict, seeds: dict, meta: dict, n_rows: int) -> str:
    import train_models as tm
    from env_manifest import manifest_markdown

    def sd_row(model: str, key: str) -> str:
        vals = [seeds[s][model][key] for s in sorted(seeds)]
        return f"{np.mean(vals):.3f} +/- {np.std(vals):.3f}"

    per_seed_rows = "\n".join(
        f"| {s} | " + " | ".join(
            f"{seeds[s][m]['top2']:.3f}" for m in MODELS
        ) + " | " + " | ".join(
            f"{seeds[s][m]['ece_cross_fitted']:.3f}" for m in MODELS
        ) + " |"
        for s in sorted(seeds)
    )

    # Every VERDICT below is derived from the run, not typed. The numbers were
    # already interpolated; the words around them were not, and words are what a
    # reader acts on. A hardcoded "negative, and cleanly so" keeps printing after it
    # stops being true -- exactly the failure this project has been bitten by.
    log_c, gbt_c = r["comparisons"]["logistic_tuned"], r["comparisons"]["gbt_tuned"]
    floor, av = r["ship_floor"], r["alpha_zero_verdict"]
    collapsed = r["collapse_to_logistic"]["folds_collapsed_to_logistic"]
    total_folds = r["collapse_to_logistic"]["total_folds"]
    n_mlp = sum(1 for v in VARIANTS.values() if v.kind == "mlp")
    mlp_selected = sum(
        r["variant_selection_counts"][n] for n in VARIANTS if VARIANTS[n].kind == "mlp"
    )

    headline = (
        "**negative, and cleanly so**"
        if collapsed > total_folds / 2 and mlp_selected == 0
        else "**mixed**: some folds selected a Variant with live neural capacity"
        if collapsed > 0
        else "**positive for the neural Variants**"
    )
    mlp_verdict = (
        f"were selected **{mlp_selected} times between them**"
        if mlp_selected == 0
        else f"were selected {mlp_selected} of {total_folds} times between them"
    )
    log_verdict = (
        "is indistinguishable from zero"
        if not log_c["ci_excludes_zero"]
        else "is distinguishable from zero"
    )
    gbt_dir = "behind" if gbt_c["delta"] < 0 else "ahead of" if gbt_c["delta"] > 0 else "level with"
    gbt_consistency = (
        "and the sign is stable across seeds"
        if gbt_c["sign_holds_in_majority"]
        else "but the sign is NOT stable across seeds"
    )
    gbt_ci_note = (
        "though the profile-level interval still includes zero"
        if not gbt_c["ci_excludes_zero"]
        else "and the profile-level interval excludes zero"
    )
    floor_verdict = (
        "both halves clear"
        if floor["stability_clears"] and floor["ece_clears"]
        else "the hard half clears, the mitigable half fails"
        if floor["stability_clears"]
        else "**the hard, unmitigable half FAILS**"
    )
    rule_verdict = (
        "fires" if len(av["seeds_where_rule_fired"]) > len(seeds) / 2 else "does not fire"
    )

    fs = r["ship_floor_across_seeds"]
    floor_seed_rows = "\n".join(
        f"| {s} | {v['top2_stability']:.3f} | {'yes' if v['stability_clears'] else '**NO**'} | "
        f"{v['ece']:.3f} |"
        for s, v in fs["per_seed"].items()
    )

    collapse_rows = "\n".join(
        f"| {s} | {v['folds_collapsed_to_logistic']} of {tm.N_FOLDS} | "
        f"{v['rows_disagreeing_with_logistic_tuned']} of {v['n_rows']} |"
        for s, v in r["collapse_to_logistic"]["per_seed"].items()
    )

    c_rows = "\n".join(
        f"| {C} | {m['ece']:.4f} | {'yes' if m['ece'] <= 0.10 else '**NO**'} | "
        f"{m['top2_stability']:.4f} | {m['top2']:.4f} |"
        for C, m in r["calibration_sensitivity_to_C"].items()
    )

    selection_rows = "\n".join(
        f"| {name} | {VARIANTS[name].axis} | {r['variant_selection_counts'][name]} | "
        f"{VARIANTS[name].rationale} |"
        for name in sorted(VARIANTS, key=lambda n: (-r["variant_selection_counts"][n], n))
    )

    def effect(comparator: str) -> str:
        c = r["comparisons"][comparator]
        direction = "ahead of" if c["delta"] > 0 else ("behind" if c["delta"] < 0 else "level with")
        return f"""### Against `{comparator}`

- **delta (top-2, sweep NN minus {comparator}) = {c['delta']:+.4f}**, 95% paired-bootstrap
  CI [{c['ci_low']:+.4f}, {c['ci_high']:+.4f}] over {c['n_resamples']} resamples of
  {c['n_profiles']} profile ids.
- The CI {"EXCLUDES" if c['ci_excludes_zero'] else "INCLUDES"} zero.
- Materiality marker (Step 2.5, |delta| >= {MATERIALITY_DELTA}): **{"cleared" if c['clears_materiality'] else "not cleared"}**
  (|delta| = {abs(c['delta']):.4f}). This is a reporting standard, not a gate: under
  ADR 0001 the neural matcher ships either way, so nothing here authorises a
  decision -- it sizes the gap.
- Per-seed deltas: {", ".join(f"{d:+.4f}" for d in c['per_seed_delta'])}.
  The pooled sign holds in **{c['seeds_agreeing_with_pooled_sign']} of {len(seeds)}** seeds,
  so it {"IS" if c['sign_holds_in_majority'] else "is NOT"} stable under the >= 3-of-5 rule.
- Read as: the sweep NN is {direction} `{comparator}` by
  {abs(c['delta']) * r['n_profiles']:.1f} profiles out of {r['n_profiles']}."""

    floor = r["ship_floor"]
    both_clear = floor["ece_clears"] and floor["stability_clears"]

    # Not guarded: main() raises unless exactly one residual Variant exists, so this
    # key is always present. The Summary dereferences it unconditionally too -- one
    # convention rather than two, which is what the earlier `is not None` here broke.
    rows = "\n".join(
        f"| {s} | {v['per_fold_alpha']} | {v['n_folds_at_zero']} | "
        f"{'FIRED' if v['no_non_linear_signal'] else 'did not fire'} |"
        for s, v in av["per_seed"].items()
    )
    leads = av["leads_round_1"]
    alpha_section = f"""
## The pre-registered alpha=0 rule

The Residual Matcher {"leads Round 1" if leads else "does NOT lead Round 1"}. Its per-fold
alpha choices are reported either way -- whether a non-linear signal exists in these
features at all is what the rule measures, and a rule consulted only when it is
convenient is not a pre-registered rule. Inner CV resolved an alpha for it in every
outer fold, including folds where a different Variant went on to win the contest,
so the record below has no holes in it.

The rule, from ADR 0003, fixed before any alpha was selected on this data:

> {av['rule']}

| seed | per-fold alpha | folds at zero | rule |
|---|---|---|---|
{rows}

**The rule fired in {len(av['seeds_where_rule_fired'])} of {len(seeds)} seeds**
({", ".join(av['seeds_where_rule_fired']) or "none"}). A Residual Matcher disqualified
by this rule is still reported in full; what the rule decides is whether it may be
the shipped neural model, not whether its numbers count.

**The consequence, per the plan's Step 6 and ADR 0003:** if the rule stands, the
shipped model becomes the best *genuinely non-linear* Variant, and the cost of that
substitution must be reported explicitly. Round 1 does not make that substitution --
choosing the replacement is Round 2's job and justifying it is the decision
document's -- but the substitution is now owed, and its cost is a real one: every
non-collapsed Variant in the table above was selected less often than the collapsed
Residual Matcher, so the replacement will be a model this round's own protocol
ranked lower.{
    "" if leads else
    " Since it does not lead Round 1, the rule changes nothing about this round's "
    "outcome and is recorded as evidence for the decision document."
}
"""

    return f"""# Neural Matcher Rework -- Round 1

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Circularity is untouched here and is a separate
> defect from Leakage: the labels reproduce the `careers.json` answer key, so every
> number below measures fidelity to a hand-authored bonus table. A better protocol
> does not make the labels less circular, and this one does not claim to.

DEV-93, plan `docs/dev-23-nn-rework-plan.md` Steps 2.2 / 2.4 / 2.5 / 2.7. Ship
Floor from ADR 0002. Vocabulary is `CONTEXT.md`'s.

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Dataset: {n_rows} rows, feature `{meta["feature_version"]}`, digest `{r["dataset_digest"]}`.
Experiment seeds: {list(r["experiment_seeds"])}.

## Summary

Round 1's result is {headline}.

1. **{collapsed} of {total_folds} (seed, outer fold) selections resolved to the
   Residual Matcher at `alpha = 0`**, which is *exactly* logistic regression. The
   {n_mlp} pure-MLP Variants -- every capacity and every regularization Variant, the
   three non-ensemble protocol ones, and the control V0 that the recorded `small_nn`
   numbers came from -- {mlp_verdict}.
2. **The pre-registered alpha=0 rule {rule_verdict}**, having fired in
   {len(av['seeds_where_rule_fired'])} of {len(seeds)} seeds: "no non-linear signal
   found". The Residual Matcher is therefore disqualified from being the shipped
   neural model, per ADR 0003.
3. **Against `logistic_tuned` the difference {log_verdict}.** delta =
   {log_c['delta']:+.4f} on top-2, CI [{log_c['ci_low']:+.4f}, {log_c['ci_high']:+.4f}],
   sign holding in {log_c['seeds_agreeing_with_pooled_sign']} of {len(seeds)} seeds.
   That is expected rather than surprising: for most folds the two are the same
   estimator.
4. **Against `gbt_tuned` the selected Variant is {gbt_dir} it**, delta =
   {gbt_c['delta']:+.4f}, {gbt_consistency}
   ({gbt_c['seeds_agreeing_with_pooled_sign']} of {len(seeds)}) --
   {gbt_ci_note} [{gbt_c['ci_low']:+.4f}, {gbt_c['ci_high']:+.4f}]. Per-seed
   consistency and the interval can disagree in flavour, which is exactly why both
   are reported rather than one summarised into the other.
5. **Ship Floor: {floor_verdict}** at the gated partition -- top-2 stability
   {floor['top2_stability']:.3f} (floor >= {floor['stability_floor']}), raw ECE
   {floor['ece']:.3f} (floor <= {floor['ece_floor']}). Re-measured across all
   {fs['n_seeds']} experiment seeds, **stability clears in
   {fs['seeds_clearing_stability']} of {fs['n_seeds']}** (mean
   {fs['stability_mean']:.3f} +/- {fs['stability_sd']:.3f}) while **ECE clears in
   {fs['seeds_clearing_ece']} of {fs['n_seeds']}**, so the two halves are not equally
   solid and the ECE verdict in particular is partition-sensitive. The ECE figure is
   the *raw* one Gate 1 gates on -- a different quantity from the cross-fitted ECE in
   the per-seed table. What drives it is the inherited regularization strength and
   the fold partition, not neural capacity, of which the evaluated configuration has
   none.

**What this does NOT say.** It does not say a neural matcher cannot clear the floor;
Round 2 has not run. It does not say the labels are sound -- Circularity is untouched.
And it does not authorise any decision: under ADR 0001 the neural matcher ships
either way, so these numbers size a gap rather than settle anything.

## !! NOT A CONTINUATION OF THE DEV-91 GATE-2 ROW !!

Everything here is produced by a **5-seed protocol**, where each experiment seed is
a complete nested run varying both the fold partition and the initialisation. The
DEV-91 Gate-2 numbers (`gbt_tuned` 0.892, `logistic_tuned` 0.849, `small_nn` 0.845,
`two_tower` 0.763) come from a single seed on one fixed partition. **These are a
different measurement, not a later reading of the same one**, and the two must not
be presented as a series.

A second reason the control is not the Gate-2 `small_nn` row: this sweep trains on
**hard labels** throughout, while Gate 2's `small_nn` additionally consumes the
panel vote distribution as soft targets. The control Variant here is the *Gate-1*
`small_nn` configuration.

{manifest_markdown(r["environment"])}
## Protocol

**All {len(VARIANTS)} Variants compete inside every outer fold's inner
{tm.INNER_SPLITS}-fold CV.** There is no separate selection stage, therefore no stage
that can leak. An earlier revision scored Variants on the outer-fold-1 training
partition -- which under {tm.N_FOLDS}-fold CV is precisely the union of the test sets of
folds 2-{tm.N_FOLDS}, so selection would have seen 100% of the evaluation data for four of
five folds. That pass is deleted, not fixed.

**How much search this is, stated accurately.** `gbt_tuned` selects from a
{len(tm.GBT_GRID)}-point grid nested in every outer fold and `logistic_tuned` from
{len(tm.LOGISTIC_C_GRID)}. The NN's {len(VARIANTS)}-point nested grid is therefore
**comparable** to what the tuned GBT already gets
({len(VARIANTS)} against {len(tm.GBT_GRID)}), and wider than the logistic one.

That still defeats "the sweep was tuned harder than the Incumbent" -- it was not -- but
it does **not** support a claim of restraint. Rev 3 of the plan claimed a "32-point"
GBT grid, which would have made this a fraction of the Incumbent's search;
`GBT_GRID` is a `product` of four 2-element lists, so it is {len(tm.GBT_GRID)}, and
the argument was overstated by 2x. Corrected in the plan and stated honestly here.

**Seeds sit outside selection.** Inner CV runs single-seed. Within a seed all three
models share outer folds, so the per-profile indicators are genuinely paired.

### The Residual Matcher's advantage in this contest, stated properly

ADR 0003 pre-registered `alpha` as an inner-CV-selected hyperparameter, so before
the {len(VARIANTS)}-way contest the Residual Matcher resolves `(alpha, C)` on the
outer-training partition -- `alpha` by argmax over
{len(tm.RESIDUAL_ALPHA_GRID)} values, on top of a `C` itself chosen by argmax over
{len(tm.LOGISTIC_C_GRID)}.

**That resolution uses the same inner splits that then rank all {len(VARIANTS)}
Variants** -- same `tr`, same `random_state`, therefore the same
`StratifiedKFold`. So the Residual Matcher enters the contest carrying a score that
is a *maximum over {len(tm.RESIDUAL_ALPHA_GRID)} configurations* on the ranking
metric itself, while each pure-MLP Variant contributes a single configuration's
score. A maximum over several draws beats a single draw on average even when
nothing differs between them, so **the Residual Matcher's inner-CV score is
optimistically biased relative to its competitors, and the selection counts below
must be read with that in mind.** Calling it merely "one extra search" would
understate it.

This is **not Leakage** in `CONTEXT.md`'s sense -- no held-out row is touched at any
point, and `test_variant_selection.py` pins that. It is selection optimism inside
the training partition, which costs the contest its fairness between Variants but
not the outer estimate its validity.

It is left in place rather than fixed because removing it means selecting `alpha` at
a third nesting level, which ADR 0003 explicitly considered and declined as not
earning its complexity. **What the bias does not do is change the direction of the
finding**, and that is worth being precise about: the Residual Matcher won mostly
*at `alpha = 0`*, so the extra freedom it enjoyed was the freedom to switch its
neural branch off. A biased contest that hands victory to the degenerate member of
the biased Variant's own grid is not evidence of non-linear signal being
over-credited; it is the same negative finding arriving by a second route.

## Which Variant won

Across all {len(seeds)} seeds x {tm.N_FOLDS} outer folds = {len(seeds) * tm.N_FOLDS} selections:

| Variant | axis | times selected | specification |
|---|---|---|---|
{selection_rows}

**Modal Variant: `{r['modal_variant']}`**{f" at (alpha, C) = {tuple(r['modal_residual_config'])}" if r['modal_residual_config'] else ""}.

**Caveat on that table: ties are broken by registry order.** `select_by_inner_cv`
keeps the first strictly-better score, so two Variants tying on inner-CV top-2
resolve to whichever is declared earlier -- and the registry declares the capacity
axis first, so ties resolve toward the LOWER-CAPACITY Variants. At n={n_rows}, an
outer training partition holds about {round(n_rows * (tm.N_FOLDS - 1) / tm.N_FOLDS)} rows
and each inner-validation split about
{round(n_rows * (tm.N_FOLDS - 1) / tm.N_FOLDS / tm.INNER_SPLITS)} of them, so a
single profile moves inner-CV top-2 by roughly
{1 / (n_rows * (tm.N_FOLDS - 1) / tm.N_FOLDS / tm.INNER_SPLITS):.3f} and exact ties
are common rather than exotic. The record
above cannot distinguish a tie-broken pick from a decisive one. The order was fixed
before any data was seen and is a defensible default under this plan's own
hypothesis -- that the current net is too large for 232 rows -- but it is a thumb on
the scale and it is disclosed rather than buried.

**In this run the tie-break favoured Variants that won nothing.** It advantages the
earliest-declared Variants, the four capacity ones, and they were selected
{sum(r['variant_selection_counts'][n] for n in VARIANTS if VARIANTS[n].axis == "capacity")}
times out of {total_folds}. So tie-breaking cannot be what kept them out of the
counts -- it was pushing the other way.

Note that the two biases in this contest point in **opposite** directions: registry
order favours the low-capacity MLP Variants, while the argmax-over-alpha described
above favours the Residual Matcher. Only the second one had any effect on the
outcome. This is a weaker statement than "the winning Variant beat the others
outright", which an earlier draft of this report made and which the alpha argmax
does not support.

## How much of this "neural matcher" is a neural network?

**This is the central finding of Round 1 and it is a negative one.** At `alpha = 0`
the Residual Matcher's predictions are bit-identical to `frozen_logistic` at the
same `C`, and the sweep inherits `C` from the same `select_by_inner_cv` call
`logistic_tuned` uses -- so in those folds the two are *the same estimator*, not
merely similar ones.

| seed | folds collapsed to logistic | profiles where the sweep NN differs from `logistic_tuned` |
|---|---|---|
{collapse_rows}

**{r['collapse_to_logistic']['folds_collapsed_to_logistic']} of
{r['collapse_to_logistic']['total_folds']} outer-fold selections resolved to exactly
logistic regression.** The row-disagreement column is the observable consequence:
the model Round 1 selected makes the same top-2 recommendation as the Incumbent for
all but a handful of the {r['n_profiles']} profiles, and in at least one seed for
every single one of them.

Read the effect-size section below with that in mind. A delta of
{r['comparisons']['logistic_tuned']['delta']:+.4f} against `logistic_tuned` is not
evidence that a neural matcher performs comparably to logistic regression; it is
mostly the measurement of a model that *is* logistic regression, compared against
itself.

## Per-seed results

Each row is a complete nested run. `mean +/- sd` is meaningful for the two
comparators too, not only for the selected Variant, because the seed varies the fold
partition for all three.

**The ECE columns here are CROSS-FITTED** (ADR 0004), which is a different quantity
from the raw ECE the Ship Floor gates on. Do not read across the two tables.

| seed | top-2 selected | top-2 logistic | top-2 gbt | x-fit ECE selected | x-fit ECE logistic | x-fit ECE gbt |
|---|---|---|---|---|---|---|
{per_seed_rows}
| **mean +/- sd** | {sd_row("sweep_nn", "top2")} | {sd_row("logistic_tuned", "top2")} | {sd_row("gbt_tuned", "top2")} | {sd_row("sweep_nn", "ece_cross_fitted")} | {sd_row("logistic_tuned", "ece_cross_fitted")} | {sd_row("gbt_tuned", "ece_cross_fitted")} |

## Effect size (Step 2.5)

**The sampling unit is the PROFILE.** Each profile's top-2 hit indicator is averaged
across the {len(seeds)} seeds first, then differenced, and the bootstrap then resamples the
{r['n_profiles']} profile ids. Treating the {r['n_profiles'] * len(seeds)} profile-seed rows
as independent would understate the standard error by about sqrt({len(seeds)}) = {np.sqrt(len(seeds)):.1f}x
and silently narrow every interval below.

**What these intervals cover:** profile sampling variability *conditional on the
seeds drawn*. They do NOT fold in seed variability -- a two-way bootstrap over
{len(seeds)} seeds would be hopelessly underpowered on the seed dimension -- which is why
the per-seed table above is reported separately rather than summarised into them.

{effect("logistic_tuned")}

{effect("gbt_tuned")}

## Ship Floor verdict (Step 2.7 / ADR 0002)

Evaluated on **one exact configuration** -- the modal Variant `{floor['configuration']}`
-- because Qualified is a property of a configuration and is never inherited by a
reconfigured model (`CONTEXT.md`).

**The determinism assertion passed before any stability number was computed**
({floor['determinism_assertion']}). That ordering is enforced in
`evaluate_ship_floor`, not remembered: `assert_deterministic` raises rather than
returning a flag, so the hard floor cannot fire on a measurement artifact.

| half | value | floor | clears? | mitigable? |
|---|---|---|---|---|
| top-2 stability | {floor['top2_stability']:.3f} | >= {floor['stability_floor']} | {"YES" if floor['stability_clears'] else "**NO**"} | no -- hard and unmitigable |
| **raw** ECE | {floor['ece']:.3f} | <= {floor['ece_floor']} | {"YES" if floor['ece_clears'] else "**NO**"} | yes -- may ship as ranking source with formula percentages |

### The hard floor under all {len(seeds)} experiment seeds

The verdict above is the Gate-1 convention: one fixed partition, seed
{floor['random_state']}. But the stability half is **hard and unmitigable** --
failing it escalates as a project-level finding rather than degrading into anything
-- while every other number in this deliverable is a 5-seed measurement. A hard
threshold resting on one draw deserves the same treatment, so it is re-measured
here. **This is reported beside the gated number, not substituted for it**;
switching the gate to a 5-seed mean after seeing the data would be moving a
threshold, not tightening one.

| seed | top-2 stability | clears >= {floor['stability_floor']}? | raw ECE |
|---|---|---|---|
{floor_seed_rows}

Stability mean {fs['stability_mean']:.3f} +/- {fs['stability_sd']:.3f}, minimum
{fs['stability_min']:.3f}. **{fs['seeds_clearing_stability']} of {fs['n_seeds']}
seeds clear the hard floor.**
{
  "The margin is not an artifact of the partition that happened to be gated."
  if fs['seeds_clearing_stability'] == fs['n_seeds'] else
  "**The hard floor is therefore partition-dependent: it clears on some fold "
  "partitions and not others, and the gated seed is one of the favourable ones.** "
  "That is a finding about the evidence available at n=232, not a passing grade."
}

**The mitigable half behaves differently, and this qualifies the verdict above.**
Raw ECE ranges {min(v['ece'] for v in fs['per_seed'].values()):.3f} to
{fs['ece_max']:.3f} across the same partitions (mean {fs['ece_mean']:.3f} +/-
{fs['ece_sd']:.3f}), and **{fs['seeds_clearing_ece']} of {fs['n_seeds']} seeds clear
the <= {floor['ece_floor']} floor**.
{
  "So the ECE failure recorded in the verdict above is specific to the gated "
  "partition rather than a property of the configuration: on most fold partitions "
  "this same model clears the floor. The gated number is not wrong -- Gate 1's "
  "convention is one fixed partition and changing it after the fact would be moving "
  "a threshold -- but reading it as 'this model is miscalibrated' would be. Combined "
  "with the C-sensitivity table below, the honest summary is that raw ECE here is "
  "governed by the inherited regularization strength and the fold partition, "
  "neither of which is a neural property."
  if fs['seeds_clearing_ece'] > fs['n_seeds'] / 2 else
  "The ECE failure is therefore consistent across partitions rather than an "
  "artifact of the gated one."
}

### Two different ECEs, and they are not comparable

The per-seed table above prints **cross-fitted** ECE (mean
{np.mean([seeds[s]['sweep_nn']['ece_cross_fitted'] for s in sorted(seeds)]):.3f}); the row
above prints **raw** ECE ({floor['ece']:.3f}). Both are honest and they measure
different things, so the same model can look calibrated in one table and fail in the
other. Gate 1 has never applied a temperature and gates on the raw number (ADR
0004), which is why the floor uses it. Stated explicitly because a reader who
carries {floor['ece']:.3f} back into the per-seed table, or the reverse, will reach a
conclusion neither number supports.

**Verdict: {
    "the modal Variant clears both halves of the Ship Floor"
    if both_clear else
    ("the modal Variant FAILS the hard stability floor. Per ADR 0002 this escalates "
     "as a project-level finding -- 'this dataset cannot support a stable 16-class "
     "neural matcher at n=232' -- rather than shipping something arbitrary"
     if not floor["stability_clears"] else
     "the modal Variant clears the hard stability floor but FAILS the mitigable ECE "
     "floor, so it may ship as the ranking source with displayed percentages falling "
     "back to the formula's")
}.**

### The ECE verdict is a statement about `C`, not about neural capacity

The modal configuration is the Residual Matcher at `alpha = 0`, so it contributed
**no neural parameters to the number above**: it is logistic regression at the `C`
its folds most often inherited. Raw ECE is strongly sensitive to that `C`, and inner
CV chose it inconsistently -- across the {r['collapse_to_logistic']['total_folds']}
outer folds every value in the grid was selected at least once.

| inherited C | raw ECE | clears <= {floor['ece_floor']}? | top-2 stability | top-2 |
|---|---|---|---|---|
{c_rows}

So the ECE floor is failed **at the modal `C`** and comfortably cleared at another
value of the same grid, by the identical estimator. Attributing that failure to the
neural architecture would be wrong: there is no neural architecture in it. The
honest reading is that `C` is unstable under this protocol and raw calibration
follows it.

For reference, the Incumbent `logistic` clears both -- read back from the
`gate1_verdict.json` in this tree rather than transcribed: ECE
{_gate1_metrics()["logistic"]["ece"]:.4f}, stability
{_gate1_metrics()["logistic"]["top2_stability"]:.4f}. So the floor is known
achievable on this data.
{alpha_section}
## What Round 1 does not answer

- Round 2 refinements, the learning curve, the serving path and the decision
  document are separate tickets. Nothing here is Selected, Servable or Deployable.
- `MATCHER_MODEL_PATH` is untouched. Note that the shipped artifact's temperature is
  no longer 1.0 (it is 1.05 since the DEV-91 export fix), and DEV-88 made the
  serving path divide logits by that field in both `predict_proba` and
  `contributions` -- so flipping the flag now changes served `matchPercent`. Earlier
  reports called that field inert; it is not.
"""


# ---------------------------------------------------------------------- main
MODELS = ("sweep_nn", "logistic_tuned", "gbt_tuned")


def calibration_sensitivity_to_C(X, y, n_classes) -> dict:
    """Raw ECE and stability of the frozen base alone, across `LOGISTIC_C_GRID`.

    Not decoration. When the selected Variant is the Residual Matcher at `alpha = 0`
    it *is* logistic regression at whatever `C` that fold inherited, so its Ship
    Floor numbers are a property of `C` and nothing else. Without this table the
    report would attribute an ECE verdict to a neural architecture that contributed
    no parameters to it.

    Raw ECE, because that is what Gate 1 gates on -- it has never applied a
    temperature.
    """
    import evaluate_matchers as em
    import train_models as tm

    out = {}
    for C in tm.LOGISTIC_C_GRID:
        oof, stability = em.cv_oof_and_stability(
            X, y, lambda C=C: frozen_logistic(C, SEED), n_classes
        )
        m = em.rank_metrics(oof, y, oof, n_classes)
        out[str(C)] = {
            "ece": float(m["ece"]),
            "top2": float(m["top2"]),
            "top2_stability": float(stability),
        }
    return out


def collapse_evidence(seeds: dict) -> dict:
    """How much of the selected 'neural matcher' is actually a neural network.

    At `alpha = 0` the Residual Matcher's predictions are bit-identical to
    `frozen_logistic` at the same `C`, and the sweep inherits `C` from the same
    `select_by_inner_cv` call `logistic_tuned` uses -- so in those folds the two
    models are the same estimator, not merely similar ones. Counted and measured
    rather than argued: the row-disagreement column is the observable consequence.
    """
    folds_at_zero, total = 0, 0
    per_seed = {}
    for s in sorted(seeds):
        variants = seeds[s]["sweep_nn"]["per_fold_variant"]
        alphas = [c[0] for c in seeds[s]["sweep_nn"]["per_fold_residual_config"]
                  ["C4_residual_matcher"]]
        collapsed = sum(
            1 for v, a in zip(variants, alphas)
            if VARIANTS[v].kind == "residual" and a == 0.0
        )
        nn = np.asarray(seeds[s]["sweep_nn"]["top2_hit"])
        lg = np.asarray(seeds[s]["logistic_tuned"]["top2_hit"])
        per_seed[s] = {
            "folds_collapsed_to_logistic": collapsed,
            "rows_disagreeing_with_logistic_tuned": int((nn != lg).sum()),
            "n_rows": int(len(nn)),
        }
        folds_at_zero += collapsed
        total += len(variants)
    return {"per_seed": per_seed, "folds_collapsed_to_logistic": folds_at_zero,
            "total_folds": total}


def _stacked_hits(seeds: dict, model: str):
    """Long-form (profile, seed) rows for `model`, aligned with `_stacked_ids`.

    Every seed contributes one indicator per profile in `train_features.parquet`
    row order, so stacking seed-blocks and tiling the ids keeps the two aligned by
    construction rather than by a join that could silently mismatch.
    """
    return np.concatenate([np.asarray(seeds[s][model]["top2_hit"]) for s in sorted(seeds)])


def _stacked_ids(seeds: dict, profile_ids):
    return np.concatenate([np.asarray(profile_ids) for _ in sorted(seeds)])


def main() -> None:
    import train_models as tm
    from dataset_guards import dataset_digest
    from env_manifest import environment_manifest

    df, X, y, _soft, careers, _arch, meta = tm.load_data()
    digest = dataset_digest(df, meta["feature_names"])
    profile_ids = df["profile_id"].tolist()
    n_classes = len(careers)

    state = _load_checkpoint(digest)
    for experiment_seed in EXPERIMENT_SEEDS:
        if str(experiment_seed) in state["seeds"]:
            continue
        print(f"seed {experiment_seed} ...", flush=True)
        state["seeds"][str(experiment_seed)] = run_one_seed(X, y, n_classes, experiment_seed)
        _save_checkpoint(state)

    seeds = state["seeds"]
    ids = _stacked_ids(seeds, profile_ids)

    # --- Step 2.5 effect sizes, paired, profile as the sampling unit.
    comparisons = {}
    for comparator in ("logistic_tuned", "gbt_tuned"):
        boot = paired_bootstrap(
            ids,
            _stacked_hits(seeds, "sweep_nn"),
            _stacked_hits(seeds, comparator),
        )
        per_seed_delta = [
            seeds[s]["sweep_nn"]["top2"] - seeds[s][comparator]["top2"] for s in sorted(seeds)
        ]
        # "Sign holds in >= 3 of 5 seeds". Counted against the sign of the pooled
        # delta, and a zero-delta seed supports neither sign.
        pooled_sign = np.sign(boot["delta"])
        boot["per_seed_delta"] = per_seed_delta
        boot["seeds_agreeing_with_pooled_sign"] = int(
            sum(1 for d in per_seed_delta if np.sign(d) == pooled_sign and d != 0)
        )
        boot["sign_holds_in_majority"] = bool(boot["seeds_agreeing_with_pooled_sign"] >= 3)
        boot["clears_materiality"] = bool(abs(boot["delta"]) >= MATERIALITY_DELTA)
        boot["ci_excludes_zero"] = bool(boot["ci_low"] > 0 or boot["ci_high"] < 0)
        comparisons[comparator] = boot

    # --- Which Variant actually won, across all 25 (seed, outer fold) selections.
    selections = [v for s in sorted(seeds) for v in seeds[s]["sweep_nn"]["per_fold_variant"]]
    counts = {name: selections.count(name) for name in VARIANTS}
    # Ties broken by registry order, the same rule the 14-way contest uses, so the
    # report has one tie-break convention rather than two. `max` keeps the first
    # maximum, and dict order is registry order.
    modal = max(counts, key=lambda n: counts[n])

    # The Ship Floor is a property of ONE exact configuration, so the residual's
    # (alpha, C) must be pinned too when it is the modal Variant.
    modal_config = None
    if VARIANTS[modal].kind == "residual":
        chosen = [
            tuple(c) for s in sorted(seeds)
            for c in seeds[s]["sweep_nn"]["per_fold_residual_config"][modal]
        ]
        modal_config = max(set(chosen), key=chosen.count)

    print(f"ship floor on the modal Variant {modal} ...", flush=True)
    floor = evaluate_ship_floor(X, y, n_classes, VARIANTS[modal], modal_config, SEED)

    print("ship floor across the 5 experiment seeds ...", flush=True)
    floor_seeds = ship_floor_across_seeds(
        X, y, n_classes, VARIANTS[modal], modal_config, EXPERIMENT_SEEDS
    )

    print("calibration sensitivity to the inherited C ...", flush=True)
    c_sensitivity = calibration_sensitivity_to_C(X, y, n_classes)
    collapse = collapse_evidence(seeds)

    # --- The pre-registered alpha=0 rule, per seed.
    # Read whenever a residual Variant exists, not only when it wins: "is there a
    # non-linear signal in these features at all?" is information the decision
    # document needs either way, and a rule only consulted when convenient is not a
    # pre-registered rule.
    # Exactly one residual Variant, asserted rather than defensively guarded: the
    # Summary and the alpha section both dereference this unconditionally, so a
    # `if residual_names:` guard here would only move a crash somewhere less
    # obvious. `test_variant_registry.py` pins the count at one.
    residual_names = [n for n, v in VARIANTS.items() if v.kind == "residual"]
    if len(residual_names) != 1:
        raise SystemExit(
            f"expected exactly one residual Variant, found {residual_names}. The "
            "pre-registered >=3-of-5 alpha rule is stated against one model; with "
            "several, 'the' per-fold alpha record is ambiguous and the rule cannot "
            "be read without choosing which one it applies to."
        )
    name = residual_names[0]
    per_seed_alpha = {
        s: tm.alpha_zero_verdict(
            [tuple(c) for c in seeds[s]["sweep_nn"]["per_fold_residual_config"][name]]
        )
        for s in sorted(seeds)
    }
    alpha_verdict = {
        "variant": name,
        "leads_round_1": bool(VARIANTS[modal].kind == "residual"),
        "per_seed": per_seed_alpha,
        "seeds_where_rule_fired": [
            s for s, v in per_seed_alpha.items() if v["no_non_linear_signal"]
        ],
        "rule": per_seed_alpha[sorted(seeds)[0]]["rule"],
    }

    results = {
        "dataset_digest": digest,
        "experiment_seeds": list(EXPERIMENT_SEEDS),
        "n_profiles": len(profile_ids),
        "variant_selection_counts": counts,
        "modal_variant": modal,
        "modal_residual_config": list(modal_config) if modal_config else None,
        "comparisons": comparisons,
        "ship_floor": floor,
        "ship_floor_across_seeds": floor_seeds,
        "calibration_sensitivity_to_C": c_sensitivity,
        "collapse_to_logistic": collapse,
        "alpha_zero_verdict": alpha_verdict,
        "per_seed": {
            s: {m: {k: v for k, v in seeds[s][m].items() if k != "top2_hit"} for m in MODELS}
            for s in sorted(seeds)
        },
        "environment": environment_manifest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    OUT_MD.write_text(_report(results, seeds, meta, len(df)), encoding="utf-8")
    print(f"wrote {OUT_MD} and {OUT_JSON}")


if __name__ == "__main__":
    main()
