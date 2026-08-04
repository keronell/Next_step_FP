"""Round 2 of the DEV-23 neural-matcher rework, and the final Ship Floor verdict.

Plan: `docs/dev-23-nn-rework-plan.md` Step 2.7 (search budget: round 1 plus round 2,
**no round 3**). Ticket: DEV-95. Vocabulary is `CONTEXT.md`'s.

Round 1 (`sweep_variants.py`, DEV-93) returned a negative finding and fired ADR
0003's pre-registered disqualification rule, whose consequence is that the shipped
model becomes "the best genuinely non-linear Variant". Round 1 cannot name that
Variant: `train_models.select_by_inner_cv` returned the argmax and discarded the
other thirteen scores, so the ranking among the never-selected Variants was computed
25 times and thrown away 25 times. DEV-95 adds the out-channel
(`select_by_inner_cv(..., scores_out=)`) and this script re-runs the contest to
collect it.

Two measuring stages, each checkpointed per experiment seed and each runnable on its
own, plus a third that only re-renders the report:

    data/venv-training/Scripts/python data/scripts/sweep_round2.py --stage scoreboard
    data/venv-training/Scripts/python data/scripts/sweep_round2.py --stage round2
    data/venv-training/Scripts/python data/scripts/sweep_round2.py --stage report

**scoreboard** re-runs Round 1's 14-way contest on the same seeds and folds and
records every Variant's inner-CV score. It runs the contest ONLY -- no outer refits,
no cross-fitted temperatures, no comparator legs -- because ranking Variants needs
nothing else, and the comparator legs are an hour of LightGBM nested CV that Round 1
already paid for. Its first output is a reproduction check: the per-fold winners must
match `round1_results.json` exactly, or no number it produces is comparable to Round
1's.

**round2** is the refinement contest, under the IDENTICAL nested protocol, fold
structure and seed count -- only the model configurations differ, which is the only
latitude DEV-95's acceptance criteria allow. Its registry is Round 1's Variants
**minus the Residual Matcher**, plus the refinements: ADR 0006 disqualified the
residual from being the shipped neural model, and a contest whose winner may not take
the prize cannot select anything. See `round2_registry`.

Reports are written UTF-8 but printed to a cp1252 console: everything that reaches
the report or a `print()` is ASCII, including the refinements' `rationale` strings.
Docstrings and comments are exempt.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# EXPERIMENT_SEEDS is imported rather than restated: identical seeds are a
# requirement of this ticket rather than a convenience, since a refinement evaluated
# on other seeds or other folds is not comparable to the round it refines.
from sweep_variants import (
    EXPERIMENT_SEEDS,
    MATERIALITY_DELTA,
    SEED,
    TRAINING_DIR,
    VARIANTS,
    Variant,
    evaluate_ship_floor,
    paired_bootstrap,
    select_variant,
    ship_floor_across_seeds,
)

ROUND1_RESULTS = TRAINING_DIR / "round1_results.json"
SCOREBOARD_JSON = TRAINING_DIR / "round2_scoreboard.json"
SCOREBOARD_CHECKPOINT = TRAINING_DIR / "round2_scoreboard_checkpoint.json"
OUT_MD = TRAINING_DIR / "nn_rework_round2.md"
OUT_JSON = TRAINING_DIR / "round2_results.json"
CHECKPOINT = TRAINING_DIR / "round2_checkpoint.json"

MODELS = ("sweep_nn", "logistic_tuned", "gbt_tuned")
# The seed whose reused comparator legs are recomputed and compared per profile.
COMPARATOR_VERIFY_SEED = 42


# ADR 0006 disqualifies the **Residual Matcher** from being the shipped neural model,
# not merely the alpha=0 point of its grid. So the substitution set is every Variant
# that is not the residual: each of them carries live neural capacity in every
# configuration, which is exactly what "genuinely non-linear" has to mean if the
# substitution is to mean anything.
def genuinely_non_linear(variants=None) -> list[str]:
    variants = VARIANTS if variants is None else variants
    return [name for name, v in variants.items() if v.kind != "residual"]


# ------------------------------------------------------------------ checkpointing
def _load_checkpoint(path: Path, digest: str) -> dict:
    """Resume a partial run, or start clean if the dataset moved.

    Keyed on the dataset digest for the reason `sweep_variants._load_checkpoint`
    gives: a checkpoint written against a different build of the features is silently
    wrong rather than obviously wrong, so it is discarded instead of merged. This
    file is separate from Round 1's, which must not be touched -- Round 1's numbers
    are a recorded measurement, not a draft.
    """
    fingerprint = _protocol_fingerprint()
    fresh = {"dataset_digest": digest, "protocol_fingerprint": fingerprint, "seeds": {}}
    if not path.exists():
        return fresh
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("dataset_digest") != digest:
        print("checkpoint was written against a different dataset build - discarding")
        return fresh
    # The digest pins the DATA. Completed seeds are fits, and a fit is only reusable
    # if the code, the registry and the packages that produced it are also unchanged.
    # Resuming across any of those mixes old and new fits into one output, stamps the
    # CURRENT environment onto cached results, and can carry a stale
    # round_1_reproduction through the drift guard on results nothing re-derived.
    # Discarding costs a recompute; not discarding costs a silently blended record.
    if saved.get("protocol_fingerprint") != fingerprint:
        print(
            "checkpoint was written under a different protocol or environment "
            "(registry, seeds, or package versions changed) - discarding rather than "
            "mixing old fits with new ones"
        )
        return fresh
    if saved.get("seeds"):
        print(f"resuming: seeds {sorted(saved['seeds'])} already complete")
    return saved


def _protocol_fingerprint() -> str:
    """What a resumed checkpoint must match, beyond the dataset digest.

    Covers the Variant registry (names AND full specifications, so a changed default
    in `nn_model.py` is caught rather than a changed name only), the experiment
    seeds, and the package/interpreter manifest. Hashed rather than stored whole so
    the checkpoint stays small; the mismatch message names the categories, and the
    committed results file records the environment in full for anyone diffing.
    """
    import hashlib

    from env_manifest import environment_manifest

    registry = round2_registry()
    payload = {
        "registry": {
            name: full_specification(variant)
            for name, variant in sorted(registry.items())
        },
        "experiment_seeds": list(EXPERIMENT_SEEDS),
        "environment": environment_manifest(),
    }
    blob = json.dumps(payload, sort_keys=True, default=repr)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _save_checkpoint(path: Path, state: dict) -> None:
    state.setdefault("protocol_fingerprint", _protocol_fingerprint())
    path.write_text(json.dumps(state), encoding="utf-8")


# --------------------------------------------------------------------- scoreboard
def scoreboard_one_seed(X, y, experiment_seed: int, variants=None) -> list[dict]:
    """The contest, and only the contest, for every outer fold of one seed.

    Returns one record per outer fold: the winner, and what all of them scored.
    Deliberately not routed through `train_models.cross_fitted_oof` -- that driver
    also refits on the outer training partition and fits three inner temperatures per
    fold, none of which a ranking needs. The selection it performs is the same
    function call either way, which is what makes the winners here comparable to
    Round 1's.
    """
    import sweep_variants as sv
    import train_models as tm

    variants = VARIANTS if variants is None else variants
    folds = []
    for i, (tr, _te) in enumerate(tm.outer_folds(X, y, random_state=experiment_seed), 1):
        scores: dict = {}
        winner, residual_config = select_variant(
            X, y, tr, random_state=experiment_seed, variants=variants, scores_out=scores,
        )
        print(f"    fold {i}: {winner}", flush=True)
        folds.append(sv.fold_record(winner, scores, residual_config))
    return folds


def reproduces_round_1(scoreboard: dict) -> dict:
    """Do the per-fold winners match what Round 1 recorded?

    The gate on every other number this script produces. The contest is a pure
    function of `(X, y, tr, random_state)`, so instrumenting it must not move a single
    selection; if one moved, either the out-channel is not inert or the environment
    is not the one Round 1 ran in, and in both cases Round 2 is not a continuation of
    Round 1 but a different experiment.
    """
    recorded = json.loads(ROUND1_RESULTS.read_text(encoding="utf-8"))
    per_seed = {}
    for seed, folds in scoreboard.items():
        was = recorded["per_seed"][seed]["sweep_nn"]["per_fold_variant"]
        now = [f["winner"] for f in folds]
        per_seed[seed] = {"round_1": was, "round_2_rerun": now, "identical": was == now}
    return {
        "per_seed": per_seed,
        "all_identical": all(v["identical"] for v in per_seed.values()),
        "n_selections": sum(len(v["round_1"]) for v in per_seed.values()),
    }


def rank_variants(scoreboard: dict, variants=None) -> dict:
    """Mean inner-CV top-2 per Variant across every (seed, outer fold) contest.

    The quantity Round 1 discarded. `mean_rank` is carried beside `mean_score`
    because the two answer different questions: a Variant can hold a respectable mean
    score while never being close to winning a single fold, and the substitution ADR
    0003 owes is a choice between models that were all beaten in all 25 contests.
    """
    variants = VARIANTS if variants is None else variants
    per_variant = {name: [] for name in variants}
    ranks = {name: [] for name in variants}
    for folds in scoreboard.values():
        for fold in folds:
            for name, score in fold["scores"].items():
                per_variant[name].append(score)
            # Rank 1 is the best. Ties take the average rank, so a Variant is neither
            # rewarded nor punished by the registry order the winner's tie-break uses.
            names = list(fold["scores"])
            values = np.array([fold["scores"][n] for n in names])
            order = (-values).argsort()
            rank = np.empty(len(names), dtype=float)
            rank[order] = np.arange(1, len(names) + 1)
            for j, name in enumerate(names):
                tied = values == values[j]
                ranks[name].append(float(rank[tied].mean()))
    out = {}
    for name in variants:
        scores = np.array(per_variant[name], dtype=float)
        out[name] = {
            "mean_score": float(scores.mean()),
            "sd_score": float(scores.std()),
            "min_score": float(scores.min()),
            "max_score": float(scores.max()),
            "mean_rank": float(np.mean(ranks[name])),
            "best_rank": float(np.min(ranks[name])),
            "times_ranked_first": int(sum(1 for r in ranks[name] if r == 1.0)),
            "n_contests": int(len(scores)),
        }
    return out


def margin_over_best_non_linear(scoreboard: dict, variants=None) -> dict:
    """Per contest: what the winner scored, and what the best genuinely non-linear
    Variant scored in the same contest.

    This is the **cost of the substitution** ADR 0006 requires to be reported
    explicitly, measured on the selection metric itself and per fold rather than
    inferred from two pooled means. Paired by construction: both numbers come from
    the same inner splits of the same training partition.
    """
    # Registry order, so ties resolve exactly as the contest itself resolves them --
    # `select_by_inner_cv` keeps the first strictly-better score, and `max` over an
    # unordered set would not reproduce that.
    non_linear = genuinely_non_linear(variants)
    margins, picks = [], []
    for folds in scoreboard.values():
        for fold in folds:
            best_any = max(fold["scores"].values())
            best_nl_name = max(non_linear, key=lambda n: fold["scores"][n])
            margins.append(best_any - fold["scores"][best_nl_name])
            picks.append(best_nl_name)
    counts = {n: picks.count(n) for n in sorted(set(picks))}
    return {
        "per_contest_margin": [float(m) for m in margins],
        "mean_margin": float(np.mean(margins)),
        "max_margin": float(np.max(margins)),
        "contests_with_zero_margin": int(sum(1 for m in margins if m == 0.0)),
        "n_contests": len(margins),
        "best_non_linear_per_contest": counts,
    }


def tie_break_incidence(scoreboard: dict, variants=None) -> dict:
    """How often the contest's winner was tied with somebody, and with whom.

    `select_by_inner_cv` keeps the first strictly-better score, so an exact tie
    resolves to whichever Variant is declared earlier. `nn_rework.md` disclosed that
    bias for Round 1 and could then show it decided nothing, because the Variants it
    favours won zero selections. Round 2 must not inherit that reassurance: its
    refinements are declared AFTER the Round-1 Variants, and at roughly 62 rows per
    inner-validation split a single profile moves inner-CV top-2 by about 0.016, so
    exact ties are common rather than exotic.

    Counted rather than argued, and per contest, because "the tie-break decided N of
    25 selections" is the only form of this disclosure a reader can act on.
    """
    variants = VARIANTS if variants is None else variants
    order = list(variants)
    tied_contests, tied_pairs = 0, []
    for folds in scoreboard.values():
        for fold in folds:
            best = max(fold["scores"].values())
            joint = [n for n in order if fold["scores"][n] == best]
            if len(joint) > 1:
                tied_contests += 1
                tied_pairs.append(joint)
    return {
        "contests_decided_by_registry_order": tied_contests,
        "n_contests": sum(len(f) for f in scoreboard.values()),
        "tied_groups": tied_pairs,
    }


def deliverable_substitution_cost(round2_seeds: dict, profile_ids) -> dict | None:
    """What the disqualification cost at the OUTER level, paired per profile.

    `margin_over_best_non_linear` prices the substitution on the inner-CV selection
    metric, which is the quantity the choice was made on but not the quantity the
    deliverable reports. ADR 0006 asks for the cost of the substitution explicitly, and
    the honest version of that is the held-out one: Round 1's selected model against
    Round 2's, over the same profiles.

    **It is exactly paired and free.** Both rounds ran the same seeds over the same
    fold partitions, so the two per-profile indicator sets line up row for row, and
    both are already recorded -- nothing is refitted to produce this.

    It does NOT contradict the report's "not a continuation" warning. That warning is
    about the two rounds' `sweep_nn` columns describing different ELIGIBLE SETS, which
    is exactly what this number prices; what would be wrong is presenting them as one
    model improving over time.

    Returns None when Round 1's checkpoint is absent (it is gitignored), because this
    is an additional reading rather than a load-bearing one.
    """
    path = TRAINING_DIR / "round1_checkpoint.json"
    if not path.exists():
        return None
    round1 = json.loads(path.read_text(encoding="utf-8"))["seeds"]
    shared = sorted(set(round1) & set(round2_seeds))
    if not shared:
        return None
    ids = np.concatenate([np.asarray(profile_ids) for _ in shared])
    boot = paired_bootstrap(
        ids,
        np.concatenate([np.asarray(round2_seeds[s]["sweep_nn"]["top2_hit"]) for s in shared]),
        np.concatenate([np.asarray(round1[s]["sweep_nn"]["top2_hit"]) for s in shared]),
    )
    boot["seeds_compared"] = shared
    boot["per_seed_delta"] = [
        round2_seeds[s]["sweep_nn"]["top2"] - round1[s]["sweep_nn"]["top2"] for s in shared
    ]
    boot["ci_excludes_zero"] = bool(boot["ci_low"] > 0 or boot["ci_high"] < 0)
    return boot


def run_scoreboard() -> dict:
    import train_models as tm
    from dataset_guards import dataset_digest
    from env_manifest import environment_manifest

    df, X, y, _soft, _careers, _arch, meta = tm.load_data()
    digest = dataset_digest(df, meta["feature_names"])

    state = _load_checkpoint(SCOREBOARD_CHECKPOINT, digest)
    for seed in EXPERIMENT_SEEDS:
        if str(seed) in state["seeds"]:
            continue
        print(f"seed {seed}: 14-Variant contest, scores recorded ...", flush=True)
        state["seeds"][str(seed)] = scoreboard_one_seed(X, y, seed)
        _save_checkpoint(SCOREBOARD_CHECKPOINT, state)

    scoreboard = state["seeds"]
    out = {
        "dataset_digest": digest,
        "experiment_seeds": list(EXPERIMENT_SEEDS),
        "round_1_reproduction": reproduces_round_1(scoreboard),
        "variant_ranking": rank_variants(scoreboard),
        "substitution_cost": margin_over_best_non_linear(scoreboard),
        "genuinely_non_linear": genuinely_non_linear(),
        "per_seed": scoreboard,
        "environment": environment_manifest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    SCOREBOARD_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {SCOREBOARD_JSON}")

    rep = out["round_1_reproduction"]
    print(f"Round 1 selections reproduced: {rep['all_identical']} "
          f"({rep['n_selections']} selections)")
    ranking = sorted(out["variant_ranking"].items(), key=lambda kv: -kv[1]["mean_score"])
    for name, m in ranking:
        print(f"  {name:24s} mean {m['mean_score']:.4f} +/- {m['sd_score']:.4f}  "
              f"mean rank {m['mean_rank']:.2f}  first in {m['times_ranked_first']}")
    sub = out["substitution_cost"]
    print(f"substitution cost: mean margin {sub['mean_margin']:.4f}, "
          f"max {sub['max_margin']:.4f}, zero in {sub['contests_with_zero_margin']} "
          f"of {sub['n_contests']} contests")
    return out


# ------------------------------------------------------------------ round 2 proper
# The refinements. At most six (plan Step 2.7; DEV-95 acceptance criteria), fixed here
# before the Round-2 contest runs and not revised after seeing its outcome -- the same
# pre-registration discipline that governs the effect-size reporting governs the
# search budget. THERE IS NO ROUND 3.
#
# All six sit on one axis, and the scoreboard is why. Read across the recovered
# ranking (`round2_scoreboard.json`, 25 contests):
#
#   C3_seed_ensemble   0.7991    V0 ensembled over 5 seeds
#   B2_dropout_0.5     0.7828    best pure MLP
#   ...                          nine more, all within 0.033 of each other
#   V0_control         0.7638    the base C3 ensembles
#   C2_sgd_cosine      0.6545    last in all 25 contests
#
# Ensembling V0 is worth **+0.0353** against the same base -- an exactly paired
# comparison, since C3's members ARE V0. Every capacity and regularization Variant
# together spans 0.033. So seed-averaging is not one lever among several; it is the
# only one Round 1 found, and it is worth more than the 0.0280 substitution cost of
# giving up the disqualified Residual Matcher. Refining anywhere else would be
# refining the axis the evidence says does nothing.
#
# The set below therefore varies the ensemble's DOSE (D1), its BASE along the three
# best-ranked non-V0 configurations (D2-D4), a combination of the two best
# regularizers (D5), and that same combination WITHOUT the ensemble (D6). D6 is the
# attribution control: it is what makes a D5 win readable as "the ensemble" or "the
# regularizers" rather than confounding the two -- the discipline plan Step 2.2
# applied when it refused to fuse C3 into C4.
#
# None of them carries an internal search, deliberately. The Residual Matcher entered
# Round 1 with a maximum over its four-point alpha grid scored on the ranking metric
# itself; a refinement with its own grid would inherit exactly that optimism.
REFINEMENTS: dict = {
    "D1_ensemble_9": Variant(
        "D1_ensemble_9", "protocol", "ensemble",
        "9 seed-averaged members instead of C3's 5 -- dose-response on the only "
        "mechanism Round 1 moved (+0.0353 over the same base)",
        {"n_members": 9}),
    "D2_ensemble_dropout_0.5": Variant(
        "D2_ensemble_dropout_0.5", "regularization", "ensemble",
        "5 members at dropout 0.5, the best-ranked pure MLP base (0.7828)",
        {"dropout": 0.5}),
    "D3_ensemble_wd_1e-2": Variant(
        "D3_ensemble_wd_1e-2", "regularization", "ensemble",
        "5 members at weight decay 1e-2, the second-best base (0.7782) and a "
        "different regularizer from D2's",
        {"weight_decay": 1e-2}),
    "D4_ensemble_84_64_16": Variant(
        "D4_ensemble_84_64_16", "capacity", "ensemble",
        "5 members of the single-hidden-layer net (0.7713) -- ensembling under the "
        "plan's own hypothesis that V0 is too large for 232 rows",
        {"hidden_sizes": (64,)}),
    "D5_ensemble_dropout_0.5_wd_1e-2": Variant(
        "D5_ensemble_dropout_0.5_wd_1e-2", "regularization", "ensemble",
        "5 members combining the two best-ranked regularizers, neither of which was "
        "tried with the other in Round 1",
        {"dropout": 0.5, "weight_decay": 1e-2}),
    "D6_dropout_0.5_wd_1e-2": Variant(
        "D6_dropout_0.5_wd_1e-2", "regularization", "mlp",
        "D5's configuration WITHOUT the ensemble -- the attribution control, so a D5 "
        "result is readable as the ensemble or as the combination, not both at once",
        {"dropout": 0.5, "weight_decay": 1e-2}),
}


def round2_registry() -> dict:
    """Round 1's eligible Variants plus the refinements.

    **The Residual Matcher is not in it, and that is the pre-registered rule
    executing rather than a judgement call.** ADR 0006 disqualifies it from being the
    shipped neural model, and Round 2's job is to produce a configuration that ships;
    a contest whose winner may not take the prize cannot select anything. Its Round-1
    numbers stand, its counterfactual score is reported per contest as the
    substitution cost, and none of that requires it to compete again.

    Everything else is identical to Round 1: same protocol, same fold structure, same
    seeds. Only the model configurations differ, which is exactly the latitude DEV-95
    allows.
    """
    eligible = {n: v for n, v in VARIANTS.items() if v.kind != "residual"}
    overlap = set(eligible) & set(REFINEMENTS)
    if overlap:
        raise SystemExit(
            f"refinement names collide with Round 1's Variants: {sorted(overlap)}. Two "
            "different configurations under one name would make the selection counts "
            "unreadable across the two rounds."
        )
    return {**eligible, **REFINEMENTS}


def full_specification(variant: Variant) -> dict:
    """Every hyperparameter of `variant`, defaults included.

    DEV-97 exports whatever this ticket selects, and "the modal Variant" is not a
    specification — it is a name whose meaning lives in a registry entry plus a
    constructor's defaults. Read from `inspect.signature` rather than transcribed, so
    a changed default in `nn_model.py` cannot leave this record quietly describing a
    model nobody trained.
    """
    import inspect

    from nn_model import NNClassifier, SeedEnsemble

    def defaults(cls) -> dict:
        return {
            name: p.default
            for name, p in inspect.signature(cls.__init__).parameters.items()
            if p.default is not inspect.Parameter.empty
        }

    if variant.kind == "ensemble":
        member = {**defaults(NNClassifier), **variant.kwargs}
        member.pop("n_members", None)
        spec = {
            "class": "nn_model.SeedEnsemble",
            "n_members": variant.kwargs.get("n_members", defaults(SeedEnsemble)["n_members"]),
            "member": {"class": "nn_model.NNClassifier", **member},
            "member_seeds": "random_state + i for i in range(n_members)",
        }
    else:
        spec = {"class": "nn_model.NNClassifier", **defaults(NNClassifier), **variant.kwargs}
    spec["axis"] = variant.axis
    spec["rationale"] = variant.rationale
    # random_state has no default by design (nn_model.NNClassifier), and the value
    # used is the Ship Floor's gated seed -- recorded rather than left implicit,
    # because a neural configuration without its seed is not one configuration.
    spec["random_state"] = SEED
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in spec.items()}


def reuse_or_recompute_comparators(X, y, n_classes, seed: int, recompute: bool,
                                   verify: bool) -> tuple[dict, dict]:
    """Round 1's comparator legs, reused by default and verified on one seed.

    `gbt_tuned` and `logistic_tuned` do not depend on the Variant registry, and within
    a seed the fold partition is a function of the seed alone -- so their Round-2
    numbers are Round-1's numbers, and recomputing all five seeds would be an hour of
    LightGBM nested CV spent reproducing a file this tree already holds.

    Reused is not the same as assumed, so one seed is recomputed and compared per
    profile. The report states which seed and what the comparison found.
    """
    import sweep_variants as sv

    # Read only on the path that needs it: `round1_checkpoint.json` is gitignored, and
    # `--recompute-comparators` exists precisely for a tree that does not have it.
    # Reading it unconditionally would make the escape hatch fail on the one input it
    # was built for.
    if recompute:
        return sv.comparator_legs(X, y, n_classes, seed), {"recomputed": True}

    path = TRAINING_DIR / "round1_checkpoint.json"
    if not path.exists():
        raise SystemExit(
            f"{path} not found, so Round 1's comparator legs cannot be reused. Either "
            "restore that checkpoint or re-run with --recompute-comparators, which "
            "refits gbt_tuned and logistic_tuned for every seed (about an hour of "
            "LightGBM nested CV) instead."
        )
    checkpoint = json.loads(path.read_text(encoding="utf-8"))["seeds"][str(seed)]
    reused = {m: checkpoint[m] for m in ("logistic_tuned", "gbt_tuned")}
    if not verify:
        return reused, {}

    fresh = sv.comparator_legs(X, y, n_classes, seed)
    check = {
        "verified_seed": seed,
        "per_model": {
            m: {
                "top2_round_1": reused[m]["top2"],
                "top2_recomputed": fresh[m]["top2"],
                "identical_top2": reused[m]["top2"] == fresh[m]["top2"],
                "profiles_disagreeing": int(
                    (np.asarray(reused[m]["top2_hit"]) != np.asarray(fresh[m]["top2_hit"])).sum()
                ),
            }
            for m in reused
        },
    }
    check["all_identical"] = all(
        v["identical_top2"] and v["profiles_disagreeing"] == 0
        for v in check["per_model"].values()
    )
    return reused, check


# -------------------------------------------------------------------------- report
# Every VERDICT below is DERIVED from the run, never typed. DEV-91 asserted "the
# pooled temperature is optimistic" twice and its own data falsified both; DEV-93
# shipped a hardcoded "nine pure-MLP Variants" when there were 12. Both were caught
# only because the numbers beside the words were computed. ASCII only -- reports are
# written UTF-8 but printed to a cp1252 console.
def _report(r: dict, seeds: dict, meta: dict, n_rows: int) -> str:
    import train_models as tm
    from env_manifest import manifest_markdown
    from sweep_variants import _gate1_metrics

    registry = round2_registry()
    # Round 1's own headline, read back from its results file rather than
    # transcribed -- a literal here would keep printing after `nn_rework.md` moved.
    round1 = json.loads(ROUND1_RESULTS.read_text(encoding="utf-8"))
    round1_collapsed = round1["collapse_to_logistic"]["folds_collapsed_to_logistic"]
    round1_total_folds = round1["collapse_to_logistic"]["total_folds"]

    floor, fs = r["ship_floor"], r["ship_floor_across_seeds"]
    log_c, gbt_c = r["comparisons"]["logistic_tuned"], r["comparisons"]["gbt_tuned"]
    sb, sub = r["round_1_scoreboard"]["variant_ranking"], r["round_1_scoreboard"]["substitution_cost"]
    rep = r["round_1_scoreboard"]["round_1_reproduction"]
    selected, spec = r["selected_variant"], r["selected_specification"]
    n_refinements = len(r["refinements"])
    ties = r["tie_break_incidence"]

    refinement_selected = selected in r["refinements"]
    refinements_won = sum(r["variant_selection_counts"][n] for n in r["refinements"])
    total_folds = sum(r["variant_selection_counts"].values())

    # Did Round 2 buy anything? Answered against the Round-1 baseline the refinements
    # were built around: the best genuinely non-linear Variant by mean inner-CV score.
    # Taken over the ELIGIBLE Variants -- the disqualified Residual Matcher tops the
    # scoreboard, so a max over the whole table would name it and every sentence built
    # on it would be about a model that may not ship.
    round1_best_nl = max(genuinely_non_linear(), key=lambda n: sb[n]["mean_score"])
    r2_rank = r["variant_ranking"]
    round2_best = max(r2_rank, key=lambda n: r2_rank[n]["mean_score"])
    refinement_gain = r2_rank[round2_best]["mean_score"] - r2_rank[round1_best_nl]["mean_score"]

    # Compared against the SELECTED Variant, not merely against "some refinement".
    # Testing `round2_best in refinements` printed "a refinement was selected and it
    # leads the contest" while the leader and the selection were two different
    # refinements -- a coherence the data did not have.
    headline = (
        "a refinement was selected, and it is also the contest leader"
        if refinement_selected and round2_best == selected
        else f"a refinement was selected, but the contest is led by a different one "
        f"(`{round2_best}`)"
        if refinement_selected
        else "**no refinement was selected in any fold**; the shipped configuration is "
        "one of Round 1's own Variants"
    )
    warranted = (
        "earned its budget" if refinements_won > 0 else "bought nothing"
    )
    floor_verdict = (
        "both halves clear"
        if floor["stability_clears"] and floor["ece_clears"]
        else "the hard half clears, the mitigable half fails"
        if floor["stability_clears"]
        else "**the hard, unmitigable half FAILS**"
    )
    final_verdict = (
        f"`{selected}` clears both halves of the Ship Floor and is the final selected "
        "configuration"
        if floor["stability_clears"] and floor["ece_clears"] else
        (f"`{selected}` clears the hard stability floor but FAILS the mitigable ECE "
         "floor, so it may ship as the RANKING source with displayed percentages "
         "falling back to the formula's (ADR 0005)"
         if floor["stability_clears"] else
         "**NO configuration clears the hard stability floor. Per ADR 0005 and the "
         "plan's Step 2.7 this ESCALATES as a project-level finding -- 'this dataset "
         "cannot support a stable 16-class neural matcher at n=232' -- rather than "
         "shipping something arbitrary. The floor is not lowered to make something "
         "pass.**")
    )

    def scoreboard_rows(ranking: dict, source: dict) -> str:
        return "\n".join(
            f"| {name} | {source[name].axis} | {m['mean_score']:.4f} +/- {m['sd_score']:.4f} | "
            f"{m['mean_rank']:.2f} | {m['times_ranked_first']} of {m['n_contests']} |"
            for name, m in sorted(ranking.items(), key=lambda kv: -kv[1]["mean_score"])
        )

    reproduction_rows = "\n".join(
        f"| {s} | {'identical' if v['identical'] else '**MOVED**'} | "
        f"{sum(1 for a, b in zip(v['round_1'], v['round_2_rerun']) if a != b)} |"
        for s, v in rep["per_seed"].items()
    )

    refinement_rows = "\n".join(
        f"| {name} | {v.axis} | {r['variant_selection_counts'][name]} | {v.rationale} |"
        for name, v in REFINEMENTS.items()
    )

    selection_rows = "\n".join(
        f"| {name} | {registry[name].axis} | {r['variant_selection_counts'][name]} | "
        f"{'refinement' if name in r['refinements'] else 'round 1'} |"
        for name in sorted(registry, key=lambda n: (-r["variant_selection_counts"][n], n))
    )

    per_seed_rows = "\n".join(
        f"| {s} | " + " | ".join(f"{seeds[s][m]['top2']:.3f}" for m in MODELS)
        + " | " + " | ".join(f"{seeds[s][m]['ece_cross_fitted']:.3f}" for m in MODELS) + " |"
        for s in sorted(seeds)
    )

    def sd_row(model: str, key: str) -> str:
        vals = [seeds[s][model][key] for s in sorted(seeds)]
        return f"{np.mean(vals):.3f} +/- {np.std(vals):.3f}"

    floor_seed_rows = "\n".join(
        f"| {s} | {v['top2_stability']:.3f} | {'yes' if v['stability_clears'] else '**NO**'} | "
        f"{v['ece']:.3f} | {'yes' if v['ece_clears'] else '**NO**'} |"
        for s, v in fs["per_seed"].items()
    )

    # The pair the control was registered for: the same configuration with and
    # without the ensemble, so a Round-2 result is readable as "the ensemble" or "the
    # regularizers" instead of confounding the two. Measured twice on exactly paired
    # configurations -- once in Round 1 (C3 against the V0 it ensembles) and once
    # here -- because one paired difference is an anecdote about one base.
    ENSEMBLED, SINGLE = "D5_ensemble_dropout_0.5_wd_1e-2", "D6_dropout_0.5_wd_1e-2"
    if ENSEMBLED in r2_rank and SINGLE in r2_rank:
        gain = r2_rank[ENSEMBLED]["mean_score"] - r2_rank[SINGLE]["mean_score"]
        round1_gain = sb["C3_seed_ensemble"]["mean_score"] - sb["V0_control"]["mean_score"]
        attribution = f"""`{SINGLE}` is `{ENSEMBLED}`'s configuration without the ensemble -- the same
dropout, the same weight decay, one network instead of five. It scored
{r2_rank[SINGLE]['mean_score']:.4f} against {r2_rank[ENSEMBLED]['mean_score']:.4f},
so **seed-averaging is worth {gain:+.4f} here**, holding the regularization fixed.

Round 1 supplies the same measurement on a different base: `C3_seed_ensemble` against
the `V0_control` it ensembles, {round1_gain:+.4f}. Two exactly paired comparisons on
two different bases, agreeing in sign, are what let this round attribute its result to
seed-averaging rather than to the regularizers it was combined with. Round 1 could not
make that attribution at all, because it recorded only which Variant won."""
    else:
        attribution = (
            "The registered attribution control is absent from this run's registry, so "
            "the ensemble's contribution is NOT separated from the configuration it "
            "was combined with. Read the ranking above as a comparison of packages."
        )

    # How concentrated the selection is. Round 1 selected one Variant in 23 of 25
    # contests, so "the modal Variant" was very nearly "the Variant". If Round 2's
    # selection is spread thin, the same phrase means something much weaker, and the
    # Ship Floor is then evaluated on a configuration the protocol picked a minority
    # of the time. Computed both ways rather than assumed either way.
    modal_share = r["variant_selection_counts"][selected] / total_folds
    round1_counts = round1["variant_selection_counts"]
    round1_modal_count = max(round1_counts.values())
    round1_modal_share = round1_modal_count / round1_total_folds
    n_variants_winning = len([n for n, c in r["variant_selection_counts"].items() if c > 0])
    dominance_note = (
        "A configuration selected by a clear majority of the contests is what makes "
        "'the selected configuration' a description of the protocol's answer rather "
        "than of its most frequent tie."
        if modal_share > 0.5 else
        f"**That is a minority of the contests, and it qualifies what this round "
        f"selected.** The protocol did not converge on one configuration: it chose "
        f"{n_variants_winning} different Variants across the contests, and the Ship "
        f"Floor below is evaluated on the most frequent of them. Read `{selected}` as "
        f"the modal answer of an unstable selection, not as a configuration the "
        f"evidence singled out -- a real finding about what n=232 can resolve, and one "
        f"the decision document should carry."
    )

    # The same substitution priced on the quantity the deliverable actually reports.
    # The margin above is on the inner-CV SELECTION metric -- the quantity the choice
    # was made on, but not the one anyone reads a model by.
    dc = r.get("substitution_cost_at_the_deliverable")
    if dc:
        deliverable_cost_section = f"""### The same cost, priced on held-out top-2

The margin above is on the inner-CV selection metric. The quantity this deliverable
reports is pooled out-of-fold top-2, so the substitution is priced there too --
**exactly paired and refitting nothing**: both rounds ran seeds
{", ".join(dc['seeds_compared'])} over the same fold partitions, so the per-profile
indicators line up row for row.

- **delta (Round-2 selected minus Round-1 selected) = {dc['delta']:+.4f}** on top-2,
  95% paired-bootstrap CI [{dc['ci_low']:+.4f}, {dc['ci_high']:+.4f}] over
  {dc['n_resamples']} resamples of {dc['n_profiles']} profile ids. The CI
  {"EXCLUDES" if dc['ci_excludes_zero'] else "INCLUDES"} zero.
- Per-seed deltas: {", ".join(f"{d:+.4f}" for d in dc['per_seed_delta'])}.
- Read as: obeying ADR 0006's disqualification costs
  {abs(dc['delta']) * r['n_profiles']:.1f} profiles out of {r['n_profiles']}
  {"against" if dc['delta'] < 0 else "in favour of"} the model Round 1 would have
  shipped.

**This is not the two rounds presented as a series.** It is the price of a candidate
set that excludes the Residual Matcher, measured against one that included it -- which
is precisely what ADR 0006 asks to be reported explicitly, and it is the reason the
"not a continuation" warning above forbids reading the `sweep_nn` columns as one model
improving rather than forbidding this comparison."""
    else:
        deliverable_cost_section = (
            "The held-out version of this cost is not computed here: Round 1's "
            "checkpoint (gitignored) is absent from this tree, so the two rounds' "
            "per-profile indicators cannot be paired."
        )

    # The selection-count tie, and how it was resolved. Registry order would otherwise
    # have picked the model DEV-97 exports, which is not a basis anyone would defend
    # if it were stated out loud -- so it is stated out loud.
    tie = r.get("selection_count_tie", {"tied_for_top_count": [selected]})
    tied_names = tie["tied_for_top_count"]
    if len(tied_names) > 1:
        others = ", ".join(f"`{n}` ({r2_rank[n]['mean_score']:.4f}, "
                           f"{r2_rank[n]['times_ranked_first']} outright)"
                           for n in tie["runners_up"])
        count_tie_note = (
            f"**That selection was a tie on count, broken on the metric.** "
            f"{len(tied_names)} Variants each took {tie['top_count']} of "
            f"{total_folds} contests: `{selected}` "
            f"({r2_rank[selected]['mean_score']:.4f} mean inner-CV top-2, "
            f"{r2_rank[selected]['times_ranked_first']} won outright) and {others}. "
            f"Resolved by {tie['resolved_by']} -- because the alternative is letting "
            "declaration order in a Python dict decide which model DEV-97 exports. "
            "No rule for aggregating per-fold winners into one configuration was "
            "pre-registered, so this resolves a tie rather than moving a threshold, "
            "and **every Variant in the tie is Ship-Floor-scored below** so the choice "
            "hides nothing."
        )
    else:
        count_tie_note = (
            f"`{selected}` held the top selection count alone, so no aggregation "
            "tie-break was needed."
        )

    # Round 1's ECE failure was specific to the gated partition -- 4 of its 5 seeds
    # cleared -- so reading it as "this model is miscalibrated" would have been wrong,
    # and `nn_rework.md` says so. Whether that holds here is a different question with
    # its own answer, and it is counted rather than carried over.
    round1_fs = round1["ship_floor_across_seeds"]
    if fs["seeds_clearing_ece"] == 0:
        ece_across_seeds_note = (
            "**The ECE failure is a property of this configuration, not of the gated "
            "partition.** Every one of the "
            f"{fs['n_seeds']} fold partitions fails the floor, and the best of them "
            f"({min(v['ece'] for v in fs['per_seed'].values()):.3f}) is still above "
            f"it. This is where Round 2 differs from Round 1 in kind rather than in "
            f"degree: Round 1's modal Variant cleared raw ECE on "
            f"{round1_fs['seeds_clearing_ece']} of {round1_fs['n_seeds']} partitions, "
            "so its gated failure was a partition effect. This one is not, and the "
            "mitigation is what makes the model shippable rather than an argument "
            "that the number is unrepresentative."
        )
    elif fs["seeds_clearing_ece"] > fs["n_seeds"] / 2:
        ece_across_seeds_note = (
            "So the gated ECE result is partition-sensitive: on most fold partitions "
            "this same configuration lands on the other side of the floor. The gated "
            "number is not wrong -- Gate 1's convention is one fixed partition -- but "
            "it is not a property of the configuration either."
        )
    else:
        ece_across_seeds_note = (
            f"**Failing the ECE floor is the common case for this configuration, not "
            f"the gated partition's peculiarity.** {fs['n_seeds'] - fs['seeds_clearing_ece']} "
            f"of {fs['n_seeds']} partitions fail it. Round 1's modal Variant cleared on "
            f"{round1_fs['seeds_clearing_ece']} of {round1_fs['n_seeds']}, so its gated "
            "failure was a partition effect and reading it as 'this model is "
            "miscalibrated' would have been wrong. That defence is not available here: "
            "the mitigation is what makes this model shippable, not an argument that "
            "the number is unrepresentative."
        )

    # Whether the tie-break mattered is COUNTED, not assumed in either direction.
    # Round 1 could disclose the same bias and then show it decided nothing; that
    # reassurance is a property of Round 1's counts and does not transfer.
    selected_was_tied = any(selected in g for g in ties["tied_groups"])
    if ties["contests_decided_by_registry_order"] == 0:
        tie_verdict = "it decided nothing this round"
        tie_consequence = (
            "No contest ended in an exact tie, so registry order resolved nothing and "
            "every selection above was decided on the metric."
        )
    elif selected_was_tied:
        tie_verdict = "it reached the selected Variant"
        tie_consequence = (
            f"`{selected}` appears in a tied group above, so **the record cannot "
            "distinguish a tie-broken pick from a decisive one** for those contests. "
            "`nn_rework.md` could disclose this same bias and then show it decided "
            "nothing, because the Variants registry order favours won zero selections "
            "in Round 1. That reassurance is a property of Round 1's counts and is "
            "not repeated here."
        )
    else:
        tie_verdict = "it did not reach the selected Variant"
        tie_consequence = (
            f"`{selected}` is in none of the tied groups above, so the tie-break "
            "changed which Variant won some contests but not which one this round "
            "selected."
        )

    # The other arm of the count tie, scored on the same floor. Without this a reader
    # cannot see what the tie-break cost or gained, only that a tie-break happened.
    alternatives = r.get("ship_floor_tied_alternatives", {})
    if alternatives:
        rows = "\n".join(
            f"| `{name}` | {v['gated']['top2_stability']:.3f} | "
            f"{'yes' if v['gated']['stability_clears'] else '**NO**'} | "
            f"{v['gated']['ece']:.3f} | "
            f"{'yes' if v['gated']['ece_clears'] else '**NO**'} | "
            f"{v['across_seeds']['seeds_clearing_stability']} of "
            f"{v['across_seeds']['n_seeds']} | "
            f"{v['across_seeds']['seeds_clearing_ece']} of "
            f"{v['across_seeds']['n_seeds']} |"
            for name, v in alternatives.items()
        )
        same_verdict = all(
            v["gated"]["stability_clears"] == floor["stability_clears"]
            and v["gated"]["ece_clears"] == floor["ece_clears"]
            for v in alternatives.values()
        )
        tied_floor_section = f"""
### The other arm of the selection-count tie, on the same floor

Scored because a tie-break that is only disclosed, and not priced, still leaves the
reader unable to see what it decided.

| configuration | stability (gated) | clears? | raw ECE (gated) | clears? | stability across seeds | ECE across seeds |
|---|---|---|---|---|---|---|
| `{selected}` (selected) | {floor['top2_stability']:.3f} | {"yes" if floor['stability_clears'] else "**NO**"} | {floor['ece']:.3f} | {"yes" if floor['ece_clears'] else "**NO**"} | {fs['seeds_clearing_stability']} of {fs['n_seeds']} | {fs['seeds_clearing_ece']} of {fs['n_seeds']} |
{rows}

{"**Both arms of the tie reach the same Ship Floor verdict**, so the tie-break moved which configuration ships but not whether one could." if same_verdict else "**The two arms of the tie reach DIFFERENT Ship Floor verdicts**, which makes the tie-break above load-bearing rather than cosmetic -- read it before relying on the verdict."}
"""
    else:
        tied_floor_section = ""

    reuse = r["comparator_reuse"]
    if reuse.get("recomputed"):
        comparator_provenance = (
            "**The comparator legs were refitted for every seed** rather than reused "
            "from Round 1's checkpoint."
        )
    else:
        detail = (
            f"identical in both models, 0 of {r['n_profiles']} profiles disagreeing"
            if reuse.get("all_identical")
            else "**the check did NOT come back clean -- see `comparator_reuse` in "
                 "round2_results.json before reading any delta below**"
        )
        comparator_provenance = f"""**The comparator legs are Round 1's, reused rather than refitted.** `gbt_tuned` and
`logistic_tuned` do not depend on the Variant registry, and within a seed the fold
partition is a function of the seed alone, so their Round-2 numbers *are* their
Round-1 numbers. Reused is not the same as assumed: seed
{reuse.get('verified_seed', 'n/a')} was recomputed from scratch and compared per
profile -- {detail}."""

    def effect(comparator: str) -> str:
        c = r["comparisons"][comparator]
        direction = "ahead of" if c["delta"] > 0 else ("behind" if c["delta"] < 0 else "level with")
        return f"""### Against `{comparator}`

- **delta (top-2, Round-2 selected minus {comparator}) = {c['delta']:+.4f}**, 95%
  paired-bootstrap CI [{c['ci_low']:+.4f}, {c['ci_high']:+.4f}] over {c['n_resamples']}
  resamples of {c['n_profiles']} profile ids.
- The CI {"EXCLUDES" if c['ci_excludes_zero'] else "INCLUDES"} zero.
- Materiality marker (Step 2.5, |delta| >= {MATERIALITY_DELTA}): **{"cleared" if c['clears_materiality'] else "not cleared"}**
  (|delta| = {abs(c['delta']):.4f}). A reporting standard, not a gate: under ADR 0004
  the neural matcher ships either way, so this sizes the gap rather than authorising
  anything.
- Per-seed deltas: {", ".join(f"{d:+.4f}" for d in c['per_seed_delta'])}.
  The pooled sign holds in **{c['seeds_agreeing_with_pooled_sign']} of {len(seeds)}** seeds,
  so it {"IS" if c['sign_holds_in_majority'] else "is NOT"} stable under the >= 3-of-5 rule.
- Read as: the Round-2 selected model is {direction} `{comparator}` by
  {abs(c['delta']) * r['n_profiles']:.1f} profiles out of {r['n_profiles']}."""

    spec_rows = "\n".join(
        f"| {k} | `{v}` |" for k, v in spec.items() if k not in ("rationale",)
    )

    # What this selection costs the serving ticket, stated here because the shape of
    # the artifact is decided by the configuration and DEV-97 inherits it.
    if spec["class"].endswith("SeedEnsemble"):
        export_note = (
            f"**This is {spec['n_members']} networks, not one, and DEV-97 inherits "
            "that.** The artifact carries every member and serve-time inference runs "
            f"all {spec['n_members']} forward passes before averaging in probability. "
            "Explainability is unaffected: integrated gradients is linear in the model "
            "function, so attribution over a probability-averaged ensemble is the "
            "average of the members' attributions (plan Step 2.2). The cost is "
            "artifact size and serve-time compute, and it is a real cost that the "
            "decision document should name rather than discover."
        )
    else:
        export_note = (
            "This is a single network, so DEV-97's artifact and serve-time cost are "
            "the ones `export_model.py` and `matcher_nn.py` were scoped against."
        )

    return f"""# Neural Matcher Rework -- Round 2 and the FINAL Ship Floor verdict

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Circularity is untouched here and is a separate defect
> from Leakage: the labels reproduce the `careers.json` answer key, so every number
> below measures fidelity to a hand-authored bonus table. A second round of search
> does not make the labels less circular, and this one does not claim to.

DEV-95, plan `docs/dev-23-nn-rework-plan.md` Step 2.7. Ship Floor from ADR 0005, the
disqualification clause from ADR 0006. Vocabulary is `CONTEXT.md`'s.

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Dataset: {n_rows} rows, feature `{meta["feature_version"]}`, digest `{r["dataset_digest"]}`.
Experiment seeds: {list(r["experiment_seeds"])} -- identical to Round 1's.

## Summary

1. **Round 1's contest was re-run to recover the evidence it discarded.**
   `select_by_inner_cv` returned the argmax and dropped the other
   {len(VARIANTS) - 1} scores, so the ranking among the Variants that were never
   selected had been computed {sub['n_contests']} times and thrown away
   {sub['n_contests']} times. DEV-95 added an additive out-channel and re-ran the
   {len(VARIANTS)}-way contest. **Every one of the {rep['n_selections']} Round-1
   selections reproduced**{"" if rep["all_identical"] else " -- NO, see the reproduction table, and treat every number below as incomparable to Round 1"}.
2. **The best genuinely non-linear Variant is `{round1_best_nl}`** at mean inner-CV
   top-2 {sb[round1_best_nl]['mean_score']:.4f} +/- {sb[round1_best_nl]['sd_score']:.4f}.
   That is the substitution ADR 0006 owed and Round 1 could not name. Its cost, paired
   per contest: the disqualified Residual Matcher scored on average
   {sub['mean_margin']:+.4f} above the best non-linear Variant on the selection metric,
   with the two level in {sub['contests_with_zero_margin']} of {sub['n_contests']} contests.
3. **Round 2 refined around that Variant, not around the Round-1 winner** -- the
   reinterpretation is stated in full below rather than applied quietly.
   {n_refinements} refinements were evaluated under the identical protocol, folds and
   seeds. Result: {headline}. The refinements took
   {refinements_won} of {total_folds} selections, so the second round {warranted}.
4. **Against the Incumbent `logistic_tuned`**, delta = {log_c['delta']:+.4f} on top-2,
   CI [{log_c['ci_low']:+.4f}, {log_c['ci_high']:+.4f}], sign holding in
   {log_c['seeds_agreeing_with_pooled_sign']} of {len(seeds)} seeds. **Against
   `gbt_tuned`**, delta = {gbt_c['delta']:+.4f}, sign holding in
   {gbt_c['seeds_agreeing_with_pooled_sign']} of {len(seeds)}.
5. **FINAL Ship Floor: {floor_verdict}** at the gated partition -- top-2 stability
   {floor['top2_stability']:.3f} (floor >= {floor['stability_floor']}), raw ECE
   {floor['ece']:.3f} (floor <= {floor['ece_floor']}). Across all {fs['n_seeds']}
   experiment seeds stability clears in {fs['seeds_clearing_stability']} of
   {fs['n_seeds']} (mean {fs['stability_mean']:.3f} +/- {fs['stability_sd']:.3f}) and
   raw ECE in {fs['seeds_clearing_ece']} of {fs['n_seeds']}.

**Verdict: {final_verdict}.**

**THERE IS NO ROUND 3.** The budget was fixed in advance (plan Step 2.7) precisely so
that "keep tuning until it wins" is unavailable, and it is now spent.

## !! NOT A CONTINUATION OF ROUND 1's HEADLINE ROW !!

Round 1's selected model was the Residual Matcher, which collapsed to logistic
regression in {round1_collapsed} of {round1_total_folds} folds -- read back from
`round1_results.json` in this tree rather than transcribed. This round's candidate set **excludes** it, so the
`sweep_nn` column here describes a different set of eligible models. The two rounds
share their protocol, folds, seeds and comparators, and nothing else. Round 1's
numbers in `nn_rework.md` are unchanged and are not superseded by anything here.

{manifest_markdown(r["environment"])}
## Why the Residual Matcher is not in this contest

ADR 0006 pre-registered that `alpha = 0` in >= 3 of 5 outer folds is "no non-linear
signal found" and **disqualifies the Residual Matcher from being the shipped neural
model**. Round 1 fired that rule in 4 of 5 seeds. A contest selects the model that
ships; entering a candidate that may not ship would produce a selection nobody could
honour, and would spend a third of this round's compute re-measuring a model whose
Round-1 numbers already stand.

This is the pre-registered rule executing, not a judgement made after seeing scores.
What is *not* discarded is its evidence: its per-contest counterfactual score is the
substitution cost reported below, computed from the same inner splits.

## The evidence Round 1 discarded

Re-running the {len(VARIANTS)}-way contest with the out-channel open must not move a
single selection -- the contest is a pure function of `(X, y, tr, random_state)`, so a
selection that moved would mean either the channel is not inert or this is not Round
1's environment.

| seed | Round-1 selections reproduced? | folds differing |
|---|---|---|
{reproduction_rows}

**{"All " + str(rep["n_selections"]) + " selections are identical." if rep["all_identical"] else "SELECTIONS MOVED -- nothing below is comparable to Round 1."}**

### What every Variant actually scored

Mean inner-CV top-2 across all {sub['n_contests']} (seed, outer fold) contests. `mean
rank` is carried beside the score because they answer different questions: a Variant
can hold a respectable mean while never coming close to winning a fold, and this table
is being read to choose between models that lost all {sub['n_contests']} contests.

"Ranked first outright" counts contests a Variant won *alone*; ties are excluded from
it and take an average rank instead, so it can be smaller than the same Variant's
selection count -- the difference is exactly the contests registry order decided.

| Variant | axis | mean inner-CV top-2 | mean rank | ranked first outright |
|---|---|---|---|---|
{scoreboard_rows(sb, VARIANTS)}

**The zero-selection Variants were not all equally beaten**, which is the finding
Round 1's selection counts could not express: a count of zero is the same number for a
Variant that was second in every fold and for one that was last in every fold.

### The cost of the substitution, paired per contest

ADR 0006 requires the cost of replacing the disqualified winner to be reported
explicitly. Measured on the selection metric, in the same contests:

- mean margin of the contest winner over the best genuinely non-linear Variant:
  **{sub['mean_margin']:+.4f}** top-2
- worst single contest: {sub['max_margin']:+.4f}
- contests where the best non-linear Variant was level with the winner:
  {sub['contests_with_zero_margin']} of {sub['n_contests']}
- which Variant was the best non-linear one, per contest:
  {", ".join(f"{n} x{c}" for n, c in sub['best_non_linear_per_contest'].items())}

{deliverable_cost_section}

## The reinterpretation of "refinements around the round-1 best"

Plan Step 2.7 budgets "round 2 (<= 6 refinements around the round-1 best)". Read
literally that instruction no longer parses: **the round-1 best is the Residual
Matcher at `alpha = 0`, which is logistic regression** -- bit-identical to it, at a `C`
inherited from the same selection call `logistic_tuned` uses. Refining around it would
mean either tuning logistic regression, which is not a neural matcher and is not what
this step exists for, or widening the `alpha` grid, which ADR 0006 explicitly calls a
protocol change rather than a tuning tweak.

**The reading adopted here, stated rather than applied silently: refine around the
best genuinely non-linear Variant** -- `{round1_best_nl}` -- because ADR 0006's
disqualification clause makes that the model which actually ships. "The round-1 best"
is read as "the best of the models still eligible to be the deliverable", which is the
only reading under which a refinement round has a purpose.

## The refinements

{n_refinements} of the 6 the budget allows, fixed before this contest ran.

| refinement | axis | times selected | rationale |
|---|---|---|---|
{refinement_rows}

**None of them carries an internal search.** The Residual Matcher entered Round 1's
contest with a score that was a maximum over its four-point `alpha` grid, evaluated on
the ranking metric itself, while every other Variant contributed a single
configuration's score -- an optimism `nn_rework.md` reports in full. A refinement with
its own inner grid would inherit exactly that bias; none has one, so the Round-2
contest is a comparison of single draws throughout.

**The search budget this round spends.** Round 1's {len(VARIANTS)} Variants plus these
{n_refinements} is {len(VARIANTS) + n_refinements} configurations, against
`gbt_tuned`'s {len(tm.GBT_GRID)}-point nested grid and `logistic_tuned`'s
{len(tm.LOGISTIC_C_GRID)}. **The neural total is now ahead of the Incumbent's**, which
the plan flagged as a real cost of a second round and asked to be stated when it was
spent. This is that statement: "the NN was not tuned harder than the alternatives" was
true after Round 1 and is no longer true after Round 2.

## Round-2 contest results

{len(registry)} Variants competed in every outer fold's inner {tm.INNER_SPLITS}-fold CV
-- {len(registry) - n_refinements} eligible Round-1 Variants plus {n_refinements}
refinements.

| Variant | axis | times selected | round |
|---|---|---|---|
{selection_rows}

**Selected: `{selected}`.**

{count_tie_note}

**The registry-order tie-break, and {tie_verdict}.** `select_by_inner_cv`
keeps the first strictly-better score, so an exact tie goes to whichever Variant is
declared earlier -- and the refinements are declared after Round 1's Variants, with
`D1` before `D2` before `D3` and so on. At roughly
{round(n_rows * (tm.N_FOLDS - 1) / tm.N_FOLDS / tm.INNER_SPLITS)} rows per
inner-validation split a single profile moves inner-CV top-2 by about
{1 / (n_rows * (tm.N_FOLDS - 1) / tm.N_FOLDS / tm.INNER_SPLITS):.3f}, so ties are
common rather than exotic. **{ties['contests_decided_by_registry_order']} of
{ties['n_contests']} contests were decided by it**, between these groups:
{"; ".join(" = ".join(g) for g in ties["tied_groups"]) or "none"}.

{tie_consequence}

### What every Variant scored in the Round-2 contest

| Variant | axis | mean inner-CV top-2 | mean rank | ranked first outright |
|---|---|---|---|---|
{scoreboard_rows(r2_rank, registry)}

Best by mean inner-CV score: `{round2_best}`, which is
{"a refinement" if round2_best in r["refinements"] else "one of Round 1's Variants"}.
Against the Variant the refinements were built around (`{round1_best_nl}`) that is a
change of {refinement_gain:+.4f} on the selection metric.

### What the attribution control shows

{attribution}

## Per-seed results

Each row is a complete nested run on the same folds for all three models. **The ECE
columns are CROSS-FITTED** (ADR 0007) -- a different quantity from the raw ECE the
Ship Floor gates on. Do not read across the two tables.

| seed | top-2 selected | top-2 logistic | top-2 gbt | x-fit ECE selected | x-fit ECE logistic | x-fit ECE gbt |
|---|---|---|---|---|---|---|
{per_seed_rows}
| **mean +/- sd** | {sd_row("sweep_nn", "top2")} | {sd_row("logistic_tuned", "top2")} | {sd_row("gbt_tuned", "top2")} | {sd_row("sweep_nn", "ece_cross_fitted")} | {sd_row("logistic_tuned", "ece_cross_fitted")} | {sd_row("gbt_tuned", "ece_cross_fitted")} |

{comparator_provenance}

## Effect size (Step 2.5)

**The sampling unit is the PROFILE.** Each profile's top-2 hit indicator is averaged
across the {len(seeds)} seeds first, then differenced, and the bootstrap then resamples
the {r['n_profiles']} profile ids. The interval covers profile sampling variability
*conditional on the seeds drawn*; it does not fold in seed variability, which is why
the per-seed table above is reported separately rather than summarised into it.

{effect("logistic_tuned")}

{effect("gbt_tuned")}

## FINAL Ship Floor verdict (Step 2.7 / ADR 0005)

Evaluated on **one exact configuration** -- `{floor['configuration']}` -- because
Qualified is a property of a configuration and is never inherited by a reconfigured
model (`CONTEXT.md`). Round 1's Ship Floor numbers describe a different configuration
and transfer nothing to this one.

**How dominant that configuration is, stated because it bears on what "selected"
means here.** `{selected}` took
{r['variant_selection_counts'][selected]} of {total_folds} selections
({modal_share:.0%}), against Round 1's modal Variant at
{round1_modal_count} of {round1_total_folds} ({round1_modal_share:.0%}). {dominance_note}

**The determinism assertion passed before any stability number was computed**
({floor['determinism_assertion']}). `assert_deterministic` raises rather than returning
a flag, so there is no code path that produces a stability number without it.

| half | value | floor | clears? | mitigable? |
|---|---|---|---|---|
| top-2 stability | {floor['top2_stability']:.3f} | >= {floor['stability_floor']} | {"YES" if floor['stability_clears'] else "**NO**"} | no -- hard and unmitigable |
| **raw** ECE | {floor['ece']:.3f} | <= {floor['ece_floor']} | {"YES" if floor['ece_clears'] else "**NO**"} | yes -- may ship as ranking source with formula percentages |

### Both halves under all {fs['n_seeds']} experiment seeds

Reported beside the gated verdict, never substituted for it: Gate 1's convention is one
fixed partition, and switching the gate to a 5-seed mean after seeing the data would be
moving a threshold rather than tightening one.

| seed | top-2 stability | clears >= {floor['stability_floor']}? | raw ECE | clears <= {floor['ece_floor']}? |
|---|---|---|---|---|
{floor_seed_rows}

Stability mean {fs['stability_mean']:.3f} +/- {fs['stability_sd']:.3f}, minimum
{fs['stability_min']:.3f}; **{fs['seeds_clearing_stability']} of {fs['n_seeds']} seeds
clear the hard floor**. Raw ECE mean {fs['ece_mean']:.3f} +/- {fs['ece_sd']:.3f},
maximum {fs['ece_max']:.3f}; **{fs['seeds_clearing_ece']} of {fs['n_seeds']} clear the
mitigable one**.

{ece_across_seeds_note}

For reference, the Incumbent `logistic` clears both -- read back from
`gate1_verdict.json` in this tree rather than transcribed: ECE
{_gate1_metrics()["logistic"]["ece"]:.4f}, stability
{_gate1_metrics()["logistic"]["top2_stability"]:.4f}. So the floor is known achievable
on this data.

{tied_floor_section}
### Against the recorded neural Gate-1 row

`gate1_verdict.json`'s `small_nn` entry is the V0 configuration measured by the same
`cv_oof_and_stability` call, on the same default partition and the same inner splits,
so it is directly comparable to the gated row above -- the two differ in the estimator
and in nothing else.

| configuration | raw ECE | top-2 stability |
|---|---|---|
| `small_nn` (V0), recorded Gate 1 | {_gate1_metrics()["small_nn"]["ece"]:.4f} | {_gate1_metrics()["small_nn"]["top2_stability"]:.4f} |
| `{selected}`, this round | {floor['ece']:.4f} | {floor['top2_stability']:.4f} |

Stability moves by {floor['top2_stability'] - _gate1_metrics()["small_nn"]["top2_stability"]:+.4f}
and raw ECE by {floor['ece'] - _gate1_metrics()["small_nn"]["ece"]:+.4f}. Qualified is
never inherited across configurations (`CONTEXT.md`), so this comparison sizes a
change rather than transferring a verdict -- the gated row above is what qualifies or
does not qualify `{selected}`.

## The final selected configuration, in full

DEV-97 exports this. A Variant name is not a specification, so every hyperparameter is
recorded -- read from the constructor's signature rather than transcribed, defaults
included.

| field | value |
|---|---|
{spec_rows}

Rationale: {spec.get("rationale", "")}

{export_note}

## What Round 2 does not answer

- Circularity is untouched. Every number here is agreement with silver labels that
  reproduce the `careers.json` answer key.
- Nothing here is Servable or Deployable. The serving path (`matcher_nn.py`), the
  export (`export_nn_model.py`), the learning curve and the decision document are
  separate tickets, and Gate-1 revalidation of the exact exported artifact is part of
  the export, not of this round.
- `MATCHER_MODEL_PATH` is untouched. The shipped artifact's temperature is 1.05, not
  1.0, and DEV-88 made the serving path divide logits by that field in both
  `predict_proba` and `contributions` -- so flipping the flag changes served
  `matchPercent`. Ranking is unaffected: temperature scaling is monotone within a row.
"""


def run_round2(recompute_comparators: bool = False) -> dict:
    """The refinement contest, the effect sizes, and the FINAL Ship Floor verdict."""
    import sweep_variants as sv
    import train_models as tm
    from dataset_guards import dataset_digest
    from env_manifest import environment_manifest

    registry = round2_registry()
    if not REFINEMENTS:
        raise SystemExit(
            "no refinements are registered, so this stage would re-run Round 1's "
            "Variants under Round 1's protocol and call the result a second round. "
            "If the finding is that Round 2 was not warranted, record that in the "
            "report rather than running an empty contest."
        )
    if len(REFINEMENTS) > 6:
        raise SystemExit(
            f"{len(REFINEMENTS)} refinements registered; the budget pre-registered in "
            "plan Step 2.7 is at most 6, and it is fixed in advance precisely so that "
            "'keep tuning until it wins' is unavailable. There is no round 3."
        )

    df, X, y, _soft, careers, _arch, meta = tm.load_data()
    digest = dataset_digest(df, meta["feature_names"])
    profile_ids = df["profile_id"].tolist()
    n_classes = len(careers)

    # Prerequisites FIRST, the convention `train_models.main()` sets: a missing or
    # stale input must fail here rather than after every fit, the Ship Floor and six
    # seed evaluations have burned hours. The refinements were chosen FROM this file,
    # so a run without it is not the experiment this script describes.
    if not SCOREBOARD_JSON.exists():
        raise SystemExit(
            f"{SCOREBOARD_JSON} not found -- run `--stage scoreboard` first. Round 2's "
            "refinements are defined from the ranking it recovers, and the report "
            "prices the substitution against it."
        )
    scoreboard = json.loads(SCOREBOARD_JSON.read_text(encoding="utf-8"))
    if scoreboard.get("dataset_digest") != digest:
        raise SystemExit(
            "round2_scoreboard.json was computed on a different dataset build - re-run "
            "`--stage scoreboard` before Round 2."
        )
    # The digest alone is not enough. It pins the DATA; the scoreboard's Round 1
    # replay pins the CODE AND ENVIRONMENT that consume it. Under a library or
    # code change the digest can match while the replayed selections move, and the
    # report below already says so in as many words ("SELECTIONS MOVED -- nothing
    # below is comparable to Round 1") -- while continuing anyway, which is how an
    # incomparable model reaches the record and, from there, the exporter.
    # Declaring incomparability and then proceeding is the contradiction; refuse.
    reproduction = scoreboard.get("round_1_reproduction") or {}
    if not reproduction.get("all_identical"):
        raise SystemExit(
            "round2_scoreboard.json does NOT reproduce Round 1's selections, so every "
            "Round 2 number computed against it would be incomparable to Round 1 - the "
            "comparison this stage exists to make. The dataset digest matches, so this "
            "is code or environment drift, not a data change. Re-run `--stage "
            "scoreboard` in the pinned training venv (data/scripts/README.md) and only "
            "proceed once the reproduction table is identical. If the drift is "
            "deliberate, Round 1 has to be re-baselined first and said so out loud."
        )

    state = _load_checkpoint(CHECKPOINT, digest)
    comparator_check = state.get("comparator_check", {})
    for seed in EXPERIMENT_SEEDS:
        if str(seed) in state["seeds"]:
            continue
        print(f"seed {seed}: Round-2 nested run ...", flush=True)
        board: list = []
        leg = sv.sweep_leg(X, y, n_classes, seed, variants=registry, scoreboard_out=board)
        comparators, check = reuse_or_recompute_comparators(
            X, y, n_classes, seed, recompute_comparators,
            verify=(seed == COMPARATOR_VERIFY_SEED),
        )
        if check:
            comparator_check = check
            state["comparator_check"] = check
        leg["fold_scoreboard"] = [
            {"winner": f["winner"], "scores": {n: float(s) for n, s in f["scores"].items()}}
            for f in board
        ]
        state["seeds"][str(seed)] = {"sweep_nn": leg, **comparators}
        _save_checkpoint(CHECKPOINT, state)

    seeds = state["seeds"]
    ids = np.concatenate([np.asarray(profile_ids) for _ in sorted(seeds)])

    def stacked(model):
        return np.concatenate(
            [np.asarray(seeds[s][model]["top2_hit"]) for s in sorted(seeds)]
        )

    comparisons = {}
    for comparator in ("logistic_tuned", "gbt_tuned"):
        boot = paired_bootstrap(ids, stacked("sweep_nn"), stacked(comparator))
        per_seed_delta = [
            seeds[s]["sweep_nn"]["top2"] - seeds[s][comparator]["top2"] for s in sorted(seeds)
        ]
        pooled_sign = np.sign(boot["delta"])
        boot["per_seed_delta"] = per_seed_delta
        boot["seeds_agreeing_with_pooled_sign"] = int(
            sum(1 for d in per_seed_delta if np.sign(d) == pooled_sign and d != 0)
        )
        boot["sign_holds_in_majority"] = bool(boot["seeds_agreeing_with_pooled_sign"] >= 3)
        boot["clears_materiality"] = bool(abs(boot["delta"]) >= MATERIALITY_DELTA)
        boot["ci_excludes_zero"] = bool(boot["ci_low"] > 0 or boot["ci_high"] < 0)
        comparisons[comparator] = boot

    deliverable_cost = deliverable_substitution_cost(seeds, profile_ids)

    board = {str(s): seeds[str(s)]["sweep_nn"]["fold_scoreboard"] for s in sorted(seeds)}
    ranking = rank_variants(board, registry)
    ties = tie_break_incidence(board, registry)

    selections = [v for s in sorted(seeds) for v in seeds[s]["sweep_nn"]["per_fold_variant"]]
    counts = {name: selections.count(name) for name in registry}
    # **Two Variants can hold the same selection count, and then registry order would
    # decide what ships.** That is an arbitrary rule deciding the deliverable, so the
    # tie is broken on the CONTEST'S OWN METRIC -- mean inner-CV top-2 over the 25
    # contests -- which is the quantity every selection above was made on. Registry
    # order survives only as the last resort if the metric ties too.
    #
    # This resolves a tie rather than moving a threshold: no rule was pre-registered
    # for aggregating per-fold winners into one configuration, and the alternative is
    # letting declaration order pick the model DEV-97 exports. Every Variant tied on
    # count still gets a full Ship Floor verdict below, so the choice hides nothing.
    top_count = max(counts.values())
    tied_for_selection = [n for n in registry if counts[n] == top_count]
    selected = max(tied_for_selection, key=lambda n: ranking[n]["mean_score"])
    runners_up = [n for n in tied_for_selection if n != selected]

    print(f"FINAL ship floor on {selected} ...", flush=True)
    floor = evaluate_ship_floor(X, y, n_classes, registry[selected], None, SEED)
    print("ship floor across the 5 experiment seeds ...", flush=True)
    floor_seeds = ship_floor_across_seeds(
        X, y, n_classes, registry[selected], None, EXPERIMENT_SEEDS
    )

    # Every Variant that tied on selection count is Ship-Floor-scored too. Reporting
    # only the winner of a tie-break would leave a reader unable to see what the other
    # arm of the tie would have shipped.
    tied_floors = {}
    for name in runners_up:
        print(f"ship floor on the tied alternative {name} ...", flush=True)
        tied_floors[name] = {
            "gated": evaluate_ship_floor(X, y, n_classes, registry[name], None, SEED),
            "across_seeds": ship_floor_across_seeds(
                X, y, n_classes, registry[name], None, EXPERIMENT_SEEDS
            ),
        }

    results = {
        "dataset_digest": digest,
        "experiment_seeds": list(EXPERIMENT_SEEDS),
        "n_profiles": len(profile_ids),
        "refinements": {n: full_specification(v) for n, v in REFINEMENTS.items()},
        "registry_size": len(registry),
        "variant_selection_counts": counts,
        "variant_ranking": ranking,
        "tie_break_incidence": ties,
        "selected_variant": selected,
        "selection_count_tie": {
            "tied_for_top_count": tied_for_selection,
            "top_count": top_count,
            "resolved_by": (
                "mean inner-CV top-2 over all contests (the contest's own metric)"
                if len(tied_for_selection) > 1 else "no tie"
            ),
            "runners_up": runners_up,
        },
        "selected_specification": full_specification(registry[selected]),
        "comparisons": comparisons,
        "substitution_cost_at_the_deliverable": deliverable_cost,
        "ship_floor": floor,
        "ship_floor_across_seeds": floor_seeds,
        "ship_floor_tied_alternatives": tied_floors,
        "comparator_reuse": comparator_check,
        "round_1_scoreboard": {
            "variant_ranking": scoreboard["variant_ranking"],
            "substitution_cost": scoreboard["substitution_cost"],
            "round_1_reproduction": scoreboard["round_1_reproduction"],
        },
        "per_seed": {
            s: {m: {k: v for k, v in seeds[s][m].items()
                    if k not in ("top2_hit", "fold_scoreboard")} for m in MODELS}
            for s in sorted(seeds)
        },
        # Carried into the results file, not left only in the gitignored checkpoint,
        # so `--stage report` needs nothing but this file.
        "per_seed_fold_scoreboard": board,
        "environment": environment_manifest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    OUT_MD.write_text(_report(results, results["per_seed"], meta, len(df)), encoding="utf-8")
    print(f"wrote {OUT_MD} and {OUT_JSON}")
    return results


def rebuild_report() -> None:
    """Re-render `nn_rework_round2.md` from the recorded results, refitting nothing.

    How the report's prose gets edited without paying for the sweep twice -- the
    property `sweep_variants` gets from its checkpoint, stated here as its own stage
    because Round 2's expensive tail (the Ship Floor, six evaluations of a
    seed-averaged ensemble) runs *after* the checkpointed seed loop and would
    otherwise be redone for a wording change.

    **Every number comes from `round2_results.json` and nothing else** -- not from the
    gitignored checkpoint -- so this works on any tree that carries the committed
    results and cannot quietly disagree with the run that produced them. Keys derived
    from the per-fold scoreboard are recomputed from the copy inside that file and
    written back, so the JSON and the report cannot end up holding different versions
    of one derivation.
    """
    import train_models as tm
    from dataset_guards import dataset_digest

    df, _X, _y, _soft, _careers, _arch, meta = tm.load_data()
    results = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    # "Results-only" is the contract, but three live inputs leak in below: `meta`
    # (feature version), `len(df)` (row count) and the Variant registry (which
    # decides ranking and tie-break interpretation). Any of them moving would rewrite
    # recorded metrics to describe a run that never happened, while keeping the old
    # numbers and digest. Validate each against what the results file recorded.
    digest = dataset_digest(df, meta["feature_names"])
    mismatches = []
    if digest != results.get("dataset_digest"):
        mismatches.append(
            f"  dataset_digest: results {results.get('dataset_digest')} != current {digest}"
        )
    if len(df) != results.get("n_profiles"):
        mismatches.append(
            f"  n_profiles: results {results.get('n_profiles')} != current {len(df)}"
        )
    registry = round2_registry()
    if len(registry) != results.get("registry_size"):
        mismatches.append(
            f"  registry_size: results {results.get('registry_size')} != "
            f"current {len(registry)}"
        )
    if mismatches:
        raise SystemExit(
            "round2_results.json was produced against different inputs:\n"
            + "\n".join(mismatches)
            + "\n`--stage report` re-derives the Variant ranking and tie-break "
            "incidence from the LIVE registry and re-renders the row count and "
            "feature version from the CURRENT dataframe, so rebuilding now would "
            "describe a run that never happened. Re-run `--stage round2`, or check "
            "out the tree the results were produced on.\n"
            "Note: a registry whose SIZE is unchanged but whose specifications moved "
            "is not detectable from what this file records - the checkpoint's "
            "protocol fingerprint is what guards that for runs from here on."
        )

    board = results["per_seed_fold_scoreboard"]
    results["variant_ranking"] = rank_variants(board, registry)
    results["tie_break_incidence"] = tie_break_incidence(board, registry)
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    OUT_MD.write_text(_report(results, results["per_seed"], meta, len(df)), encoding="utf-8")
    print(f"rewrote {OUT_MD} and refreshed derived keys in {OUT_JSON} "
          "-- nothing was refitted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("scoreboard", "round2", "report"), required=True)
    parser.add_argument(
        "--recompute-comparators", action="store_true",
        help="refit gbt_tuned and logistic_tuned for every seed instead of reusing "
             "Round 1's identical legs (needed on a tree without round1_checkpoint.json)",
    )
    args = parser.parse_args()
    if args.stage == "scoreboard":
        run_scoreboard()
    elif args.stage == "report":
        rebuild_report()
    else:
        run_round2(recompute_comparators=args.recompute_comparators)


if __name__ == "__main__":
    main()
