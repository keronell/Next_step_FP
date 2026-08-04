"""DEV-96: the learning curve, and the balance-controlled control curve.

Plan: `docs/dev-23-nn-rework-plan.md` Step 2.6. Vocabulary is `CONTEXT.md`'s.

**The curve is EVIDENCE, not a gate.** Under ADR 0004 the neural matcher ships
either way; this sizes whether more labels would close the gap to the alternatives,
which is a direct input to whether funding a bigger dataset is worth it. It is not a
re-selection, and nothing here reopens the search budget spent in DEV-95.

Run from repo root, in the hash-pinned training venv (`data/scripts/README.md`;
`Scripts/` rather than `bin/` on Windows):

    data/venv-training/Scripts/python data/scripts/learning_curve.py --stage curve
    data/venv-training/Scripts/python data/scripts/learning_curve.py --stage report

**curve** fits every (point, seed) and checkpoints after each one. The comparator
legs are nested LightGBM and logistic at every point, which is most of the compute
and all of the risk of a killed run; the unit is one (point, seed) because that is
the largest piece whose loss is cheap and the smallest that is independently
meaningful. **report** re-renders `learning_curve.md` from
`learning_curve_results.json` alone, refitting nothing -- prose gets edited without
paying for the fits twice, which is the property `sweep_round2.py --stage report`
established and this run needs for the same reason.

Reports are written UTF-8 but printed to a cp1252 console, so everything reaching
the report or a `print()` is ASCII. Docstrings and comments are exempt.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

# The fraction the live protocol uses, kept as the source of the 15% arm rather than
# restated, so the curve's rule and `NNClassifier`'s default cannot drift apart.
from nn_model import DEFAULT_VAL_FRACTION, SeedEnsemble
from sweep_variants import EXPERIMENT_SEEDS, TRAINING_DIR

OUT_MD = TRAINING_DIR / "learning_curve.md"
OUT_JSON = TRAINING_DIR / "learning_curve_results.json"
CHECKPOINT = TRAINING_DIR / "learning_curve_checkpoint.json"
ROUND2_RESULTS = TRAINING_DIR / "round2_results.json"

# The curve's own outer protocol -- three folds, not the gates' five, because the
# smallest point holds 48 rows. Every number this script produces is therefore NOT
# comparable to a 5-fold gate number, which the report states rather than implies.
CURVE_FOLDS = 3
# Two inner folds for comparator selection, at EVERY point. At n=48 an outer training
# partition holds two rows of every class, and a 3-fold inner split of that loses a
# class from an inner training subset -- sklearn warns rather than raises, and the
# estimator then emits fewer probability columns, so the selection metric would read
# top-2 indices that mean different careers. Applied identically everywhere, so this
# is one protocol rather than a per-point accommodation.
CURVE_INNER_SPLITS = 2

COMPARATORS = ("logistic_tuned", "gbt_tuned")
MODELS = ("curve_nn", *COMPARATORS)


# ------------------------------------------------------------ the validation rule


def validation_size(n_train: int, n_classes: int) -> int:
    """`max(n_classes, ceil(0.15 * n_train))` -- ONE rule, applied at every point.

    The `n_classes` arm is what makes the small points legal at all. Under the curve's
    3-fold protocol the plain 15% rule asks for 5 validation rows at n=48, 8 at n=80
    and 12 at n=116, and a stratified split over 16 classes cannot produce any of
    them; plan Step 2.6 tabulates exactly that as the constraint shaping the design.

    The rejected alternative was a frozen epoch budget, and the reason is worth
    keeping next to the code: the optimal epoch count genuinely falls as n falls, so a
    budget tuned at n=232 would systematically over-train the small-n points and
    MANUFACTURE the very narrowing this curve exists to test for. Architecture and
    hyperparameters are frozen; the epoch count is still chosen per fit by early
    stopping under this rule.

    At n=48 the rule puts 16 of 32 training rows into validation, leaving one training
    example per class. That is why n=48 is annotated "protocol floor" and excluded
    from the test rather than quietly dropped.
    """
    return max(n_classes, math.ceil(DEFAULT_VAL_FRACTION * n_train))

# --------------------------------------------------------------- the subsampler
# Three per class, and that number is forced twice over rather than chosen.
# `StratifiedKFold(3)` -- the curve's dedicated outer protocol -- needs three members
# of every class in whatever it is handed, and 16 classes x 3 is exactly 48, the
# smallest curve point. So the floor is what makes n=48 a legal point at all, and it
# is also what makes n=48 "1 training example per class" once a third of the rows go
# to the held-out fold and the validation rule takes half of what is left.
CLASS_FLOOR = 3

# Plan Step 2.6. n=48 is REPORTED and EXCLUDED from the test -- it is a protocol
# floor, not a data-size measurement -- and it is shown so nobody can claim the
# hardest point was quietly dropped.
CURVE_POINTS = (48, 80, 116, 174, 232)

# The balance-controlled control curve: uniform k per class, so balance is held FIXED
# while n moves. `game-dev` has exactly 5 labels in the full 232, which caps uniform
# balance at k=5, and k=3 is dropped for the same protocol-floor reason as n=48 --
# which leaves two points. It is therefore explicitly a two-point sanity check and is
# barred from carrying any trend weight (plan Step 2.6).
CONTROL_K = (4, 5)
CONTROL_POINTS = tuple(k * 16 for k in CONTROL_K)  # 64, 80 at the 16-career catalog

# The subsample is a function of the CURVE POINT alone and does not vary with the
# experiment seed. Plan Step 2.6 computes the Delta-gap CI over "the 80 profiles
# common to both points", and that is one set only if every seed cuts the same
# subsample; a per-seed draw would leave the profile-as-unit bootstrap ragged. The
# cost, disclosed in the report rather than buried: the curve is conditional on ONE
# subsample draw at each point and does not average over subsample sampling.
SUBSAMPLE_SEED = 42


# ------------------------------------------------------- the pre-registered reading
def delta_gap_bootstrap(profile_ids, nn_large, comp_large, nn_small, comp_small,
                        **kwargs) -> dict:
    """`Delta-gap = gap(large) - gap(small)`, with `gap = comparator top-2 - NN top-2`.

    A NEGATIVE delta is **narrowing**: the comparator's lead over the neural matcher
    is smaller at the larger point, which is the direction "more data would close the
    gap" predicts.

    All four legs are long-form (profile, seed) indicator arrays over the SAME profile
    ids -- the profiles common to both points, which exist only because the subsamples
    nest. The contrast is computed by handing two composites to
    `sweep_variants.paired_bootstrap` rather than by writing a second resampler:

        a = comp_large + nn_small      b = nn_large + comp_small
        mean(a) - mean(b) = (comp_large - nn_large) - (comp_small - nn_small)

    That function owns the sampling unit -- it averages a profile's rows before
    differencing and then resamples profile IDS, so a profile enters a resample with
    all of its seeds or with none -- and both of those operations are linear, so the
    contrast passes through them exactly. Reusing it is what keeps this interval the
    same KIND of interval as every other one in the deliverable, rather than a second
    implementation that could disagree with `test_paired_bootstrap.py`'s contract.
    """
    from sweep_variants import paired_bootstrap

    nn_large, comp_large = np.asarray(nn_large, float), np.asarray(comp_large, float)
    nn_small, comp_small = np.asarray(nn_small, float), np.asarray(comp_small, float)
    out = paired_bootstrap(
        profile_ids, comp_large + nn_small, nn_large + comp_small, **kwargs
    )
    out["gap_large"] = float(comp_large.mean() - nn_large.mean())
    out["gap_small"] = float(comp_small.mean() - nn_small.mean())
    out["ci_excludes_zero"] = bool(out["ci_low"] > 0 or out["ci_high"] < 0)
    # Recorded separately from the verdict: the pre-registered vocabulary has two
    # values and this is not one of them, but an interval that excludes zero on the
    # widening side is a real observation and must not vanish into "inconclusive".
    out["widening_excludes_zero"] = bool(out["ci_low"] > 0)
    out["verdict"] = delta_gap_verdict(out)
    return out


def delta_gap_verdict(boot: dict) -> str:
    """The pre-registered reading, in exactly the two values it pre-registered.

    "Narrowing" iff the CI excludes zero in the narrowing direction. **Everything else
    is "flat / inconclusive"**, and no trend is claimed from a point-estimate slope --
    the discipline plan Step 2.6 imposed when it replaced rev 2's non-overlapping-CIs
    proxy. A large negative delta whose interval covers zero reads the same as a delta
    of zero, and that is deliberate.

    A CI excluding zero on the WIDENING side is "flat / inconclusive" here too,
    because the rule says "anything else" and a verdict vocabulary invented after
    seeing the data is not a pre-registered rule. It is a real observation and it is
    NOT swallowed: `widening_excludes_zero` records it, and the report prints it as an
    explicit disclosure marked as outside the pre-registered categories. Reporting it
    beside the verdict rather than as the verdict is the same treatment the Ship Floor
    gives its across-seed numbers.
    """
    return "narrowing" if boot["ci_high"] < 0 else "flat / inconclusive"


def class_floored_subsample(labels, n: int, floor: int = CLASS_FLOOR,
                            random_state: int = SUBSAMPLE_SEED) -> np.ndarray:
    """`n` row indices: `floor` of every class, then the surplus drawn proportionally.

    **Nested by construction, which is a requirement and not a convenience.** The
    pre-registered reading of the curve is `Delta-gap = gap(232) - gap(80)` computed
    over the profiles common to both points, and that set only exists if the smaller
    subsample is a subset of the larger. So this does not apportion seats
    independently at each `n` -- a proportional-rounding rule can hand a class FEWER
    seats at a larger house size (the Alabama paradox), and nesting would break
    without anything failing. Instead it fixes one global ordering of the surplus rows
    and every curve point is a PREFIX of it, which makes nesting a property of the
    construction rather than of the arithmetic.

    The ordering: within each class, surplus rows are ranked by a seeded shuffle and
    given the key `(rank + 0.5) / class_surplus_size`. Sorting every surplus row by
    that key interleaves the classes, and a prefix cut at threshold `t` holds
    `round(t * class_surplus)` rows of each class -- the divisor form (Sainte-Lague),
    chosen over the obvious `(rank + 1) / size` because that one cuts at
    `floor(t * size)` and systematically over-serves the largest class: it put
    frontend at 12 rather than 11 at n=80 and pushed the skew there to 4.0 against the
    3.7 plan Step 2.6 pre-registered. With this key the first `K` surplus rows hold
    each class in proportion to its surplus, and the balance table comes out as the
    plan states it -- max:min skew 1.0 at n=48, 3.7 at n=80, 9.4 at n=232.

    Keys collide whenever two classes have equally many surplus rows, and those ties
    are broken by a seeded random draw. That is an arbitrary resolver deciding which
    profiles land in a curve point, so its incidence is counted by
    `tie_break_incidence` and printed rather than left implicit.
    """
    labels = np.asarray(labels)
    classes = np.unique(labels)
    if n < floor * len(classes):
        raise ValueError(
            f"n={n} is below the class floor: {len(classes)} classes at {floor} rows "
            f"each already needs {floor * len(classes)}. StratifiedKFold(3) would lose "
            "a class from a fold and the top-2 columns would stop meaning the same "
            "careers across sub-models."
        )
    if n > len(labels):
        raise ValueError(f"n={n} exceeds the {len(labels)} rows available")

    floor_idx, surplus_keyed = _ordered_pools(labels, classes, floor, random_state)
    take = n - floor * len(classes)
    chosen = np.concatenate([floor_idx, np.array([r for _, _, r in surplus_keyed[:take]],
                                                 dtype=int)]) if take else floor_idx
    return np.sort(chosen.astype(int))


def uniform_subsample(labels, k: int, random_state: int = SUBSAMPLE_SEED) -> np.ndarray:
    """Exactly `k` rows of every class -- the balance-controlled control curve.

    Nested in `k` for the same reason the main curve nests in `n`, and drawn from the
    same per-class ordering, so the control points sit inside the full table rather
    than beside it.

    `k` cannot exceed the rarest class, which is the whole reason this curve has two
    points instead of five: at the 16-career catalog `game-dev`'s 5 labels cap it at
    n=80, and k=3 is dropped for the same protocol-floor reason n=48 is annotated. Two
    points cannot describe a trend and the report says so rather than implying one.
    """
    labels = np.asarray(labels)
    classes = np.unique(labels)
    orders = _class_orders(labels, classes, random_state)
    rarest = min(len(rows) for rows in orders.values())
    if k > rarest:
        raise ValueError(
            f"k={k} exceeds the rarest class, which has only {rarest} rows. Uniform "
            "balance is capped there, which is why the control curve is two points "
            "and not a trend."
        )
    return np.sort(np.concatenate([orders[c][:k] for c in classes]).astype(int))


def class_balance(labels, idx) -> dict:
    """The class composition of one subsample, and its max:min skew.

    Printed beside every point's gap because the confound is severe and pushes the
    OPPOSITE way from the data-size effect: class-floored subsampling makes the
    small-n points more balanced, so a gap that narrows with n could be a balance
    effect rather than a data effect. A curve that reported only `n` would be
    unreadable on that point, and the reader would have no way to know.
    """
    counts = np.bincount(np.asarray(labels)[idx], minlength=len(np.unique(labels)))
    present = counts[counts > 0]
    return {
        "n": int(len(idx)),
        "max_class": int(present.max()),
        "min_class": int(present.min()),
        "skew": float(present.max() / present.min()),
        "counts": counts.tolist(),
    }


def tie_break_incidence(labels, points=CURVE_POINTS, floor: int = CLASS_FLOOR,
                        random_state: int = SUBSAMPLE_SEED) -> dict:
    """How many rows each curve point's membership owed to the random tie-break.

    Two classes with equally many surplus rows produce IDENTICAL ordering keys -- on
    the real label counts three classes have 12 surplus rows and two have 8 -- so when
    such a key sits astride a curve point's cut, a seeded draw and not the key decides
    which of those rows is in the subsample. DEV-95's review caught `max()` resolving
    the shipped configuration by Python dict declaration order; the lesson recorded
    from it is that an arbitrary resolver is counted and printed, never argued about.

    Returns, per point, the size of the straddling key group and the rows in it. Zero
    at n=48 (no surplus is taken) and at n=232 (all of it is), which is the sanity
    check that the number is measuring the cut rather than the ordering.
    """
    labels = np.asarray(labels)
    classes = np.unique(labels)
    _floor_idx, keyed = _ordered_pools(labels, classes, floor, random_state)

    out = {}
    for n in points:
        take = n - floor * len(classes)
        contested: list[int] = []
        if 0 < take < len(keyed) and keyed[take - 1][0] == keyed[take][0]:
            boundary = keyed[take - 1][0]
            contested = [row for key, _tie, row in keyed if key == boundary]
        out[n] = {
            "n": n,
            "rows_decided_by_tie_break": len(contested),
            "contested_rows": contested,
        }
    return out


# ----------------------------------------------------- the frozen configuration
def frozen_configuration() -> tuple:
    """The Variant DEV-95 selected, read from its record rather than retyped.

    Plan Step 2.6 freezes "architecture and hyperparameters at the selected
    configuration", and a Variant NAME is not a configuration -- its meaning lives in
    a registry entry plus a constructor's defaults. So the registry entry is looked up
    AND checked against `selected_specification` in `round2_results.json`: every field
    that record carries must still resolve to the same value, or the curve would be
    measuring something other than the model DEV-97 exports while every test passed.

    A field the record does not carry is allowed -- this ticket adds an inert
    `val_size` argument, which appears in the computed specification and not in a
    record written before it existed. A field it does carry with a different value is
    not, and raises.

    **The selected configuration is a 5-member ensemble**, so the curve measures an
    ensemble: every fit below is five networks, and the report says so because a
    reader will assume one.
    """
    from sweep_round2 import full_specification, round2_registry

    if not ROUND2_RESULTS.exists():
        raise SystemExit(
            f"{ROUND2_RESULTS} not found. The curve freezes the configuration DEV-95 "
            "selected; without that record there is nothing to freeze."
        )
    record = json.loads(ROUND2_RESULTS.read_text(encoding="utf-8"))
    name = record["selected_variant"]
    variant = round2_registry()[name]
    # Through JSON, because that is the form the record is in: `full_specification`
    # flattens top-level tuples only, so a nested `hidden_sizes` would compare as
    # (64, 32) against the recorded [64, 32] and report drift that is not there.
    computed = json.loads(json.dumps(full_specification(variant)))
    recorded = record["selected_specification"]

    def drift(a: dict, b: dict, where: str) -> list[str]:
        out = []
        for key, recorded_value in b.items():
            if isinstance(recorded_value, dict):
                out += drift(a.get(key, {}), recorded_value, f"{where}{key}.")
            elif a.get(key, "<missing>") != recorded_value:
                out.append(f"{where}{key}: recorded {recorded_value!r}, now "
                           f"{a.get(key, '<missing>')!r}")
        return out

    moved = drift(computed, recorded, "")
    if moved:
        raise SystemExit(
            f"the registry entry for {name} no longer reproduces the configuration "
            f"recorded in round2_results.json: {'; '.join(moved)}. The curve must "
            "freeze the model that was selected, not a later edit of it."
        )
    return variant, recorded


def build_frozen_nn(variant, random_state: int, n_val: int):
    """The frozen configuration, with the curve's validation size and nothing else
    changed. `SeedEnsemble` forwards `**member_kwargs` to every member, so `val_size`
    reaches all five networks."""
    if variant.kind != "ensemble":
        raise SystemExit(
            f"{variant.name} is kind {variant.kind!r}; this curve was written for the "
            "5-member ensemble DEV-95 selected and its cost model assumes one."
        )
    return SeedEnsemble(random_state=random_state, val_size=n_val, **variant.kwargs)


# --------------------------------------------------------------- the curve points
@dataclass(frozen=True)
class CurvePoint:
    """One point on one of the two curves, with the rows it is measured on."""

    label: str
    curve: str  # "main" | "control"
    n: int
    rows: tuple
    note: str = ""


def curve_points(labels) -> list[CurvePoint]:
    """Both curves' points, in report order.

    The main curve's subsamples nest; so do the control curve's; and both are drawn
    from one per-class ordering, so the control points sit inside the full table
    rather than beside it. n=48 carries its protocol-floor annotation HERE, attached
    to the point, so no consumer can report it without it.
    """
    points = []
    for n in CURVE_POINTS:
        rows = class_floored_subsample(labels, n)
        note = ""
        if n == min(CURVE_POINTS):
            note = ("protocol floor -- 1 training example per class after the "
                    "validation rule, not a data-size measurement")
        points.append(CurvePoint(f"n={n}", "main", n, tuple(rows.tolist()), note))
    for k, n in zip(CONTROL_K, CONTROL_POINTS):
        rows = uniform_subsample(labels, k)
        points.append(CurvePoint(
            f"uniform k={k} (n={n})", "control", n, tuple(rows.tolist()),
            "balance held fixed; two points, barred from carrying trend weight",
        ))
    return points


# ------------------------------------------------------------------- the fitting
def _guard_columns(model, name: str, n_classes: int, point: str):
    """A fitted estimator that lost a class emits fewer probability columns, and every
    top-2 index after it means a different career. `cv_oof_and_stability` guards the
    gate's version of this; the curve deliberately trains on partitions small enough
    that it could actually happen, so it guards its own.

    `classes_` is read without a fallback on purpose: an estimator that does not
    expose it is one this guard cannot check, and defaulting to "assume it is fine"
    would turn the guard off for exactly the case nobody anticipated."""
    found = len(model.classes_)
    if found != n_classes:
        raise SystemExit(
            f"{name} at {point} was fitted on a partition missing a class: it emits "
            f"{found} probability columns, expected {n_classes}. Its top-2 indices no "
            "longer name the same careers as the other models', so the gap at this "
            "point would be a comparison of mislabelled sets. Raise the class floor "
            "(learning_curve.CLASS_FLOOR) rather than reading this run."
        )
    return model


def run_point_seed(X, y, n_classes, point: CurvePoint, seed: int, variant) -> dict:
    """All three models, on the SAME 3-fold partition of the SAME subsample.

    Sharing the partition within a (point, seed) is what makes the gap paired: the
    bootstrap differences per-profile indicators, which means nothing if the models
    saw different training rows.

    **The comparators are NESTED at every point, not frozen.** Freezing would force a
    choice between an arbitrary configuration -- which is no longer `gbt_tuned`, the
    model the rest of this deliverable reports a gap against -- and one selected on
    the full 232 rows, which would have seen data outside every subsample below 232
    and is Leakage in the sense `CONTEXT.md` reserves the word for. Nesting is the
    only option that is neither arbitrary nor leaky, and it costs 16x on the GBT leg.
    """
    from sklearn.model_selection import StratifiedKFold

    import train_models as tm

    rows = np.array(point.rows)
    Xs, ys = X[rows], y[rows]
    hits = {m: np.zeros(len(rows)) for m in MODELS}
    n_vals: list[int] = []
    configs: dict = {m: [] for m in COMPARATORS}

    folds = StratifiedKFold(CURVE_FOLDS, shuffle=True, random_state=seed).split(Xs, ys)
    for tr, te in folds:
        n_val = validation_size(len(tr), n_classes)
        n_vals.append(n_val)

        nn = build_frozen_nn(variant, seed, n_val).fit(Xs[tr], ys[tr])
        _guard_columns(nn, "curve_nn", n_classes, point.label)
        # The rule asked for n_val rows; this is what the split actually held out.
        for member in nn.members_:
            if member.n_val_ != n_val:
                raise SystemExit(
                    f"validation split at {point.label} held out {member.n_val_} rows, "
                    f"not the {n_val} the rule specifies"
                )
        probs = {"curve_nn": nn.predict_proba(Xs[te])}

        for name, grid, fit in (
            ("logistic_tuned", tm.LOGISTIC_C_GRID, tm.fit_logistic),
            ("gbt_tuned", tm.GBT_GRID, tm.fit_gbt),
        ):
            def guarded(params, Xtr, ytr, _name=name):
                return _guard_columns(fit(params, Xtr, ytr), _name, n_classes, point.label)

            config = tm.select_by_inner_cv(
                Xs, ys, tr, grid, guarded, random_state=seed,
                inner_splits=CURVE_INNER_SPLITS,
            )
            configs[name].append(list(config) if isinstance(config, tuple) else config)
            probs[name] = guarded(config, Xs[tr], ys[tr]).predict_proba(Xs[te])

        for name, p in probs.items():
            top2 = np.argsort(-p, axis=1)[:, :2]
            hits[name][te] = [float(ys[te][i] in top2[i]) for i in range(len(te))]

    return {
        m: {"top2": float(hits[m].mean()), "top2_hit": hits[m].tolist()} for m in MODELS
    } | {"validation_sizes": n_vals, "selected_configs": configs}


def _class_orders(labels, classes, random_state: int) -> dict:
    """One seeded priority ordering of the rows of each class.

    The single source of both curves' membership: the main curve takes a floor plus a
    prefix of the interleaved surplus, the control curve takes a prefix of each class
    outright. Drawing them from one ordering is what makes both nested inside the full
    table and inside each other, and it is why the two curves are not two unrelated
    random experiments that happen to share a dataset.
    """
    rng = np.random.default_rng(random_state)
    return {c: rng.permutation(np.flatnonzero(np.asarray(labels) == c)) for c in classes}


def _ordered_pools(labels, classes, floor: int, random_state: int):
    """The floor rows, and the surplus rows in the one global order every point cuts.

    Shared by `class_floored_subsample` and `tie_break_incidence` so the count of
    tie-broken positions describes the ordering that was actually used, rather than a
    second construction of it that could drift.
    """
    orders = _class_orders(labels, classes, random_state)
    tie_rng = np.random.default_rng(random_state + 1)
    floor_rows: list[int] = []
    keyed: list[tuple[float, float, int]] = []
    for c in classes:
        order = orders[c]
        if len(order) < floor:
            raise ValueError(
                f"class {c!r} has {len(order)} rows, below the floor of {floor}"
            )
        floor_rows.extend(order[:floor].tolist())
        surplus = order[floor:]
        for rank, row in enumerate(surplus):
            # (rank + 0.5) / len(surplus): a prefix cut at threshold t holds
            # round(t * len(surplus)) of this class, so the cut is proportional rather
            # than floored. The second element is the tie-break, drawn once per row --
            # two classes with equally many surplus rows produce identical keys, and
            # something has to order them.
            keyed.append(((rank + 0.5) / len(surplus), float(tie_rng.random()), int(row)))
    keyed.sort()
    return np.array(sorted(floor_rows), dtype=int), keyed


# ------------------------------------------------------------------- the analysis
def point_gaps(per_seed: dict, profile_ids) -> dict:
    """Each comparator's lead over the neural matcher at one point, with its CI.

    The same paired bootstrap the rest of the deliverable uses -- profile as the
    sampling unit, a profile's seeds averaged before differencing -- so a gap here is
    the same KIND of quantity as the Round-2 effect sizes, measured under a different
    protocol. Positive means the comparator is ahead.
    """
    from sweep_variants import paired_bootstrap

    seeds = sorted(per_seed)
    ids = np.concatenate([np.asarray(profile_ids) for _ in seeds])

    def stacked(model):
        return np.concatenate([np.asarray(per_seed[s][model]["top2_hit"]) for s in seeds])

    out = {}
    for comparator in COMPARATORS:
        boot = paired_bootstrap(ids, stacked(comparator), stacked("curve_nn"))
        boot["ci_excludes_zero"] = bool(boot["ci_low"] > 0 or boot["ci_high"] < 0)
        out[comparator] = boot
    return out


def delta_gap(points: dict, small: str, large: str, common_ids) -> dict:
    """`Delta-gap = gap(large) - gap(small)` over the profiles common to both points.

    "Common" is the SMALLER point's profiles, because the subsamples nest -- and that
    is the whole reason nesting is a requirement rather than a convenience. The larger
    point's indicators are restricted to those same profiles here, so the two gaps
    describe one population rather than two.
    """
    small_ids = list(points[small]["profile_ids"])
    keep = [small_ids.index(pid) for pid in common_ids]
    large_ids = list(points[large]["profile_ids"])
    keep_large = [large_ids.index(pid) for pid in common_ids]

    seeds = sorted(points[small]["per_seed"])
    ids = np.concatenate([np.asarray(common_ids) for _ in seeds])

    def leg(point: str, model: str, rows):
        return np.concatenate(
            [np.asarray(points[point]["per_seed"][s][model]["top2_hit"])[rows]
             for s in seeds]
        )

    out = {}
    for comparator in COMPARATORS:
        out[comparator] = delta_gap_bootstrap(
            ids,
            nn_large=leg(large, "curve_nn", keep_large),
            comp_large=leg(large, comparator, keep_large),
            nn_small=leg(small, "curve_nn", keep),
            comp_small=leg(small, comparator, keep),
        )
    return out


# --------------------------------------------------------------- checkpointing
def _load_checkpoint(digest: str) -> dict:
    """Resume a partial run, or start clean if the dataset moved.

    The unit is one (point, seed). The comparator legs are nested LightGBM at every
    point -- 16 grid points times 2 inner folds plus a refit, per outer fold -- which
    is where the hours are, and this environment kills long jobs around the 5-hour
    mark. Keyed on the dataset digest for the reason `sweep_variants` gives: a
    checkpoint written against another build of the features is silently wrong rather
    than obviously wrong, so it is discarded instead of merged.
    """
    if not CHECKPOINT.exists():
        return {"dataset_digest": digest, "units": {}}
    saved = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if saved.get("dataset_digest") != digest:
        print("checkpoint was written against a different dataset build - discarding")
        return {"dataset_digest": digest, "units": {}}
    if saved.get("units"):
        print(f"resuming: {len(saved['units'])} (point, seed) units already complete")
    return saved


# -------------------------------------------------------------------------- report
# Every VERDICT below is DERIVED from the run, never typed. The record on this is
# three for three: DEV-91 asserted "the pooled temperature is optimistic" and its own
# data falsified it, DEV-93 shipped a hardcoded "nine pure-MLP Variants" when there
# were 12, and DEV-95's first draft claimed the selected Variant led the contest when
# the leader and the selection were different refinements. Numbers beside typed words
# is how each was caught, so the words are computed too.
#
# ASCII only in everything that reaches the report or the console.
def _report(r: dict, meta: dict) -> str:
    from env_manifest import manifest_markdown

    points = r["points"]
    # Ordered by n explicitly rather than by dict insertion order: the control note
    # below reads the first entry as the smaller point, and a report whose direction
    # claim depended on JSON key order would be one edit away from being backwards.
    def by_size(curve):
        return sorted((p for p in points if points[p]["curve"] == curve),
                      key=lambda p: points[p]["n"])

    main_points, control = by_size("main"), by_size("control")
    anchor, far = r["delta_gap"]["small_point"], r["delta_gap"]["large_point"]
    dg = r["delta_gap"]["per_comparator"]

    def curve_rows(names):
        out = []
        for p in names:
            d = points[p]
            gaps = " | ".join(
                f"{d['gaps'][c]['delta']:+.4f} [{d['gaps'][c]['ci_low']:+.4f}, "
                f"{d['gaps'][c]['ci_high']:+.4f}]" for c in COMPARATORS
            )
            tops = " | ".join(f"{d['top2_mean'][m]:.3f} +/- {d['top2_sd'][m]:.3f}"
                              for m in MODELS)
            out.append(
                f"| {p} | {d['balance']['skew']:.2f} | {d['balance']['max_class']}:"
                f"{d['balance']['min_class']} | "
                f"{'/'.join(str(v) for v in d['validation_size'])} | {tops} | {gaps} |"
            )
        return "\n".join(out)

    def verdict_line(comparator: str) -> str:
        v = dg[comparator]
        return (
            f"- **`{comparator}`: {v['verdict'].upper()}.** Delta-gap = "
            f"{v['delta']:+.4f}, 95% paired-bootstrap CI [{v['ci_low']:+.4f}, "
            f"{v['ci_high']:+.4f}] over {v['n_resamples']} resamples of "
            f"{v['n_profiles']} profile ids. gap({far}) = {v['gap_large']:+.4f} against "
            f"gap({anchor}) = {v['gap_small']:+.4f}. The CI "
            f"{'EXCLUDES' if v['ci_excludes_zero'] else 'INCLUDES'} zero."
        )

    narrowing = [c for c in COMPARATORS if dg[c]["verdict"] == "narrowing"]
    widened = [c for c in COMPARATORS if dg[c]["widening_excludes_zero"]]
    # Plain text: the callers wrap it in emphasis, and a headline carrying its own
    # `**` produced nested markers that render as literal asterisks.
    headline = (
        "narrowing against " + " and ".join(f"`{c}`" for c in narrowing)
        if len(narrowing) == len(COMPARATORS) else
        "narrowing against " + " and ".join(f"`{c}`" for c in narrowing)
        + " and flat / inconclusive against the other" if narrowing else
        "flat / inconclusive against both comparators"
    )
    widening_note = (
        "\n**Outside the pre-registered vocabulary, and disclosed rather than "
        "substituted for the verdict:** the interval excludes zero on the WIDENING "
        "side for " + " and ".join(f"`{c}`" for c in widened) + ". The rule says "
        "anything that is not narrowing is flat / inconclusive, and inventing a third "
        "verdict after seeing the data would not be a pre-registered rule -- so the "
        "verdict above stands as written and this sits beside it.\n"
        if widened else ""
    )
    ties = r["subsample_tie_breaks"]
    tied_points = [n for n, v in ties.items() if v["rows_decided_by_tie_break"]]

    control_note = "(the control curve did not run)"
    if len(control) == 2:
        a, b = control

        def control_line(c: str) -> str:
            lo, hi = points[a]["gaps"][c]["delta"], points[b]["gaps"][c]["delta"]
            move = hi - lo
            # A sign comparison against the main curve is only worth making when the
            # main curve HAS a sign. Where its Delta-gap CI covers zero, "agrees" and
            # "disagrees" are the same statement about noise, and saying either would
            # be reading a direction out of an interval that does not have one.
            if not dg[c]["ci_excludes_zero"]:
                agreement = (
                    "and the main curve's Delta-gap is itself indistinguishable from "
                    f"zero ([{dg[c]['ci_low']:+.4f}, {dg[c]['ci_high']:+.4f}]), so "
                    "comparing signs against it carries no information"
                )
            elif move * dg[c]["delta"] > 0:
                agreement = ("the same sign as the main curve's Delta-gap "
                             f"({dg[c]['delta']:+.4f}), so the direction survives "
                             "holding balance fixed")
            else:
                agreement = ("the OPPOSITE sign to the main curve's Delta-gap "
                             f"({dg[c]['delta']:+.4f}), which is what a balance "
                             "effect rather than a data effect would look like")
            return (f"- `{c}`: gap {lo:+.4f} at {a} against {hi:+.4f} at {b}, a move "
                    f"of {move:+.4f} -- {agreement}.")

        control_note = "\n".join(control_line(c) for c in COMPARATORS)

    # A control point and a main point can land on the SAME n with different balance,
    # and when they do that pair isolates balance at fixed n far better than the
    # control curve's own two points do. Found rather than designed: it exists because
    # game-dev's label count caps the uniform curve at the same 80 the main curve's
    # anchor uses. Reported only when the pair exists.
    equal_n = [(m, c) for m in main_points for c in control
               if points[m]["n"] == points[c]["n"]]
    equal_n_note = ""
    if equal_n:
        # Which pair, stated, because picking the first of several would be an
        # arbitrary resolver deciding what a section says -- the thing DEV-95's review
        # established gets counted rather than assumed away.
        m, c = equal_n[0]
        equal_n_choice = (
            "" if len(equal_n) == 1 else
            f" ({len(equal_n)} such pairs exist; this is the smallest by n)"
        )
        rows = "\n".join(
            f"- `{comp}`: gap {points[m]['gaps'][comp]['delta']:+.4f} at skew "
            f"{points[m]['balance']['skew']:.2f} against "
            f"{points[c]['gaps'][comp]['delta']:+.4f} at skew "
            f"{points[c]['balance']['skew']:.2f} -- "
            f"{'WIDER' if points[c]['gaps'][comp]['delta'] > points[m]['gaps'][comp]['delta'] else 'NARROWER'}"
            " when the classes are made uniform."
            for comp in COMPARATORS
        )
        wider = [c2 for c2 in COMPARATORS
                 if points[c]["gaps"][c2]["delta"] > points[m]["gaps"][c2]["delta"]]
        if len(wider) == len(COMPARATORS):
            balance_direction = (
                "What it does bear on is the DIRECTION plan Step 2.6 assumed: it "
                "warned that better balance at small n might flatter the neural "
                "matcher and so manufacture an apparent narrowing. Here the gap is "
                "wider against both comparators when the classes are made uniform, "
                "which is the opposite direction -- so on this pair the confound is "
                "not working the way the warning anticipated."
            )
        elif wider:
            balance_direction = (
                "The direction is not consistent across the two comparators -- wider "
                "against " + " and ".join(f"`{c2}`" for c2 in wider) + " and not "
                "against the other -- so it bears on plan Step 2.6's assumption about "
                "which way the confound pushes without settling it either way."
            )
        else:
            balance_direction = (
                "The gap is narrower against both comparators when the classes are "
                "made uniform, which is the direction plan Step 2.6 assumed when it "
                "warned that an observed narrowing might be a balance effect. That "
                "warning is therefore live rather than idle for this data."
            )
        equal_n_note = f"""
### The two n={points[m]['n']} points, which differ in balance and not in size{equal_n_choice}

`{m}` and `{c}` hold the same number of rows and differ in how those rows are
distributed across the careers -- and in which rows they are, since they are not
nested in each other. Comparing them isolates BALANCE at fixed n, which is
the thing the main curve cannot do -- and it exists by accident rather than design,
because `game-dev`'s label count happens to cap the uniform curve at the same n the
main curve's anchor point uses.

{rows}

**Read this carefully, because it is easy to over-claim, and it carries no
interpretive weight beyond a sanity check** -- plan Step 2.6 bars the control curve
from carrying any, and this pair is made of control-curve data. The two points do not
share profiles, so this is not a paired comparison and no CI is computed across it.
More importantly the uniform point changes the TEST rows as well as the training rows:
top-2 agreement on a balanced test set is a harder measurement than on a skewed one,
because there is no dominant class to be right about by default. So a wider gap here
is partly a harder measurement and not only a harder training set. {balance_direction}
"""

    # Where the neural matcher is measurably behind at all, per point. The Delta-gap
    # is a statement about how the gap MOVES; this is the statement about whether
    # there is a gap, and a reader who only reads "flat / inconclusive" would come
    # away without it.
    behind = {
        c: [p for p in main_points
            if points[p]["gaps"][c]["ci_excludes_zero"] and points[p]["gaps"][c]["delta"] > 0]
        for c in COMPARATORS
    }
    largest = main_points[-1]
    protocol_floor = [p for p in main_points if points[p]["note"]]

    def presence_line(c: str) -> str:
        # The protocol-floor point is named as such wherever it is counted. It is a
        # legitimate observation that the gap is wide at n=48 and NOT a data-size
        # observation, and a bare count would let a reader take it for one.
        named = [p + (" -- the protocol floor" if p in protocol_floor else "")
                 for p in behind[c]]
        return (
            f"- `{c}`: the gap CI excludes zero at {len(behind[c])} of "
            f"{len(main_points)} points"
            + (f" ({'; '.join(named)})" if named else "")
            + f". At {largest} it is {points[largest]['gaps'][c]['delta']:+.4f} "
            f"[{points[largest]['gaps'][c]['ci_low']:+.4f}, "
            f"{points[largest]['gaps'][c]['ci_high']:+.4f}]."
        )

    gap_presence = "\n".join(presence_line(c) for c in COMPARATORS)
    # Every claim below is anchored at the smallest point that is NOT the protocol
    # floor. n=48 is annotated "not a data-size measurement", so a growth claim that
    # started there would be a data-size claim resting on the one point the plan
    # excludes from data-size claims. It is still shown in the table.
    floor_free = [p for p in main_points if p not in protocol_floor]
    base = floor_free[0]

    def growth(model: str) -> float:
        return points[largest]["top2_mean"][model] - points[base]["top2_mean"][model]

    nn_growth = growth("curve_nn")
    comp_growth = {c: growth(c) for c in COMPARATORS}
    # "Steeply" is a word about a magnitude, so it is earned rather than typed: the
    # threshold is the materiality marker Step 2.5 already uses for a top-2 delta.
    steep = "steeply" if abs(nn_growth) >= 0.02 else "slightly"
    rose, fell = ([c for c in COMPARATORS if comp_growth[c] > 0],
                  [c for c in COMPARATORS if comp_growth[c] < 0])
    if len(rose) == len(COMPARATORS):
        comparator_clause = "and so do both comparators"
    elif rose:
        comparator_clause = ("and so does " + " and ".join(f"`{c}`" for c in rose)
                             + ", while " + " and ".join(f"`{c}`" for c in fell)
                             + " does not")
    else:
        comparator_clause = "while neither comparator does"
    growth_sentence = (
        f"The neural matcher itself {'improves' if nn_growth > 0 else 'declines'} "
        f"{steep} with n -- from {points[base]['top2_mean']['curve_nn']:.3f} top-2 at "
        f"{base} to {points[largest]['top2_mean']['curve_nn']:.3f} at {largest}, "
        f"{nn_growth:+.3f} -- {comparator_clause} "
        f"({', '.join(f'`{c}` {comp_growth[c]:+.3f}' for c in COMPARATORS)})."
    )

    skews = [points[p]["balance"]["skew"] for p in main_points]
    skew_monotone = skews == sorted(skews)
    skew_span = f"{min(skews):.2f} at {main_points[0]} rising to {max(skews):.2f} at {largest}"
    floor_note = "".join(
        f"\n**{p} is annotated \"{points[p]['note']}\".** It is reported so nobody can "
        "claim the hardest point was quietly dropped, and it is EXCLUDED from the "
        "pre-registered test below.\n"
        for p in protocol_floor
    )
    # Nested selection fits the grid on every inner fold and then refits once;
    # freezing is a single fit. Computed rather than eyeballed -- an earlier draft
    # printed the grid size as the multiplier and was out by a factor of two.
    gbt_cost = r["gbt_grid_size"] * r["curve_inner_splits"] + 1

    # Plan Step 2.4 pt 5 requires the per-seed results as a table rather than summarised
    # into the intervals, because the intervals do not fold in seed variability. Shown
    # for the two points the Delta-gap is computed between -- those are the ones the
    # headline rests on, and five seeds times seven points would bury them.
    seed_rows = "\n".join(
        f"| {p} | {s} | "
        + " | ".join(f"{points[p]['per_seed'][s][m]['top2']:.3f}" for m in MODELS)
        + " |"
        for p in (anchor, far) for s in sorted(points[anchor]["per_seed"])
    )
    spec = r["frozen_configuration"]["specification"]
    header = "| point | skew | max:min | n_val | top-2 " + " | top-2 ".join(MODELS) \
        + " | gap vs " + " | gap vs ".join(COMPARATORS) + " |"
    rule = "|---" * (4 + len(MODELS) + len(COMPARATORS)) + "|"

    return f"""# Neural Matcher Rework -- the learning curve

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Circularity is untouched here and is a separate defect
> from Leakage: the labels reproduce the `careers.json` answer key, so every number
> below measures fidelity to a hand-authored bonus table. Measuring that fidelity at
> five dataset sizes does not make it less circular, and this report does not claim
> it does.

DEV-96, plan `docs/dev-23-nn-rework-plan.md` Step 2.6. Vocabulary is `CONTEXT.md`'s.

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Dataset: {r['n_rows']} rows, feature `{meta["feature_version"]}`, digest `{r['dataset_digest']}`.
Experiment seeds: {list(r['experiment_seeds'])}.

## Summary

1. **The gap is {headline}** under the pre-registered rule, which asks only whether
   the CI on Delta-gap excludes zero in the narrowing direction.
2. **{growth_sentence}** More data {'plainly helps' if nn_growth > 0 else 'does not help'}
   the model; what it does not do, measurably, is change how it stands RELATIVE to the
   alternatives. Those are different claims and only the second is what the verdict
   above refers to.
3. **The class-balance confound is not controlled by the main curve.** Class-floored
   subsampling puts the max:min skew at {skew_span}, so balance
   and n {'move together at every point below' if skew_monotone else 'are correlated but not monotonically'}.
4. **The curve measures a FIVE-MEMBER ENSEMBLE**, because that is what DEV-95
   selected. Every neural fit here is {spec['n_members']} networks.
5. **These numbers are not comparable to any gate number.** Different fold count,
   different inner protocol, subsampled data.

## !! NOT COMPARABLE TO THE 5-FOLD GATE NUMBERS !!

Everything here comes from a **dedicated {r['curve_folds']}-fold protocol on subsampled
data**, with comparator selection under {r['curve_inner_splits']} inner folds. Gate 1,
Gate 2, Round 1 and Round 2 all use {r['gate_folds']} outer folds and
{r['gate_inner_splits']} inner ones on all {r['n_rows']} rows. A top-2 number below is
a different measurement from a top-2 number there, not a later reading of the same
one, and the two must not be presented as a series. The Round-2 effect sizes remain
the deliverable's statement of where the neural matcher stands; this report is only
about how that standing MOVES with n.

## What this measures, and what it is for

**The curve is evidence, not a gate.** Under ADR 0004 the neural matcher ships either
way. What this sizes is whether more labels would close the gap to the alternatives --
a direct input to whether funding a bigger dataset is worth it, and the most
actionable output of DEV-23. It is not a re-selection and it cannot become one.

**The frozen model is FIVE networks, not one.** Plan Step 2.6 freezes architecture and
hyperparameters at the selected configuration, and DEV-95 selected
`{r['frozen_configuration']['name']}` -- a `{spec['class']}` of {spec['n_members']}
`NNClassifier` members seeded `random_state + i`, at dropout
{spec['member']['dropout']} and weight decay {spec['member']['weight_decay']}, every
other hyperparameter at the defaults. **Every fit on the neural leg below is
{spec['n_members']} fits.** A reader who assumes one network will misread the compute,
and will misread what "the model" means when DEV-97 exports it.

The specification is read from `selected_specification` in `round2_results.json` and
checked against the registry entry field by field, so the curve cannot quietly measure
a later edit of the configuration DEV-95 chose.

**Epoch count is NOT frozen.** Freezing the configuration is not freezing the epoch
budget: early stopping still chooses the epoch per fit, under one validation rule at
every point. A frozen budget tuned at n={points[largest]['n']} would over-train the
small-n points and manufacture the very narrowing this curve tests for.

**The validation rule, one rule everywhere:** `n_val = max(n_classes,
ceil({r['val_fraction']} * n_train))`. It is expressed through an additive
absolute-size argument rather than a per-point fraction, because `val_fraction` is a
float handed to `train_test_split` and `n_val / n_train` is not guaranteed to round
back to the integer it came from. Every fit asserts that the split held out exactly
`n_val` rows. The argument's default is inert, so the control Variant and `small_nn`'s
recorded Gate-1 numbers still describe the same estimator.

**The comparators are NESTED at every point, not frozen at one configuration.** This
is a design decision plan Step 2.6 left open, and the comparison means something
different depending on the answer, so it is stated rather than assumed.
`gbt_tuned` re-selects from its {r['gbt_grid_size']}-point grid and `logistic_tuned`
from its {r['logistic_grid_size']} at every (point, fold, seed) -- {gbt_cost}x the GBT
cost of freezing, since selecting costs {r['gbt_grid_size']} grid points times
{r['curve_inner_splits']} inner folds plus the refit, against one fit. The alternative was rejected on
correctness rather than budget: freezing means either an arbitrary configuration,
which is no longer the `gbt_tuned` the rest of this deliverable reports a gap against,
or one selected on all {r['n_rows']} rows -- which would have seen data outside every
subsample below {r['n_rows']}, and that is Leakage in the sense `CONTEXT.md` reserves
the word for, at four of the five points.

**The comparator legs are computed FRESH, not reused from Round 1 or Round 2.** Those
rounds could legitimately reuse each other's, because within a seed the fold partition
is a function of the seed alone *under the same protocol*. This is a different
protocol, so a reused leg would be a model scored on a different partition -- and
nothing would have failed.

{manifest_markdown(r["environment"])}
## The class-balance confound

Class-floored stratified subsampling gives every class at least {r['class_floor']}
rows, and on this data that puts the skew at {skew_span} across the main curve --
so the SMALL-n points are {'MORE' if skew_monotone else 'NOT uniformly more'} balanced
than the large ones. Balance and n therefore move together, and plan Step 2.6 expects
them to push in opposite directions: small n harder for data-size reasons, easier for
balance reasons. **An observed narrowing could be a balance effect.** The skew is printed beside every gap for exactly that reason, and
the control curve below is the attempt -- a limited one -- to separate them.

## The main curve

`gap` is the comparator's top-2 lead over the neural matcher; positive means the
comparator is ahead. Each gap is a paired bootstrap over that point's own profiles,
with the profile as the sampling unit and a profile's {len(r['experiment_seeds'])}
seeds averaged before differencing -- the same machinery, and the same kind of
interval, as the Round-2 effect sizes.

{header}
{rule}
{curve_rows(main_points)}
{floor_note}
**Whether there is a gap at all, which is a different question from whether it
moves.** The pre-registered reading below is about the MOVEMENT; a reader who takes
"flat / inconclusive" as "no gap" would have it backwards.

{gap_presence}

## The pre-registered reading

The quantity is **Delta-gap = gap({far}) - gap({anchor})**, computed over the
{r['delta_gap']['n_common_profiles']} profiles common to both points. That set exists
only because the subsamples are NESTED -- {anchor}'s rows are a subset of {far}'s --
which is a requirement of this design rather than a convenience, and is pinned by
`data/scripts/tests/test_learning_curve.py`.

**"Narrowing" means the CI on Delta-gap excludes zero in the narrowing direction.**
Anything else is reported as flat / inconclusive. **No trend is claimed from a
point-estimate slope**, which is the rule that replaced rev 2's non-overlapping-CIs
proxy -- a low-power test of a quantity nobody wanted.

Note that the `gap({far})` printed below is computed over those
{r['delta_gap']['n_common_profiles']} common profiles and will therefore NOT equal the
`{far}` row of the table above, which is over all {points[far]['n']}. Both are
correct; only the one below is comparable to `gap({anchor})`, and comparing the two
gaps on one population is the whole point of restricting to the common set.

{verdict_line("logistic_tuned")}
{verdict_line("gbt_tuned")}

**What these intervals cover**, stated because it is easy to assume more: profile
sampling variability *conditional on the seeds drawn*. They do NOT fold in seed
variability -- a two-way bootstrap over {len(r['experiment_seeds'])} seeds would be
hopelessly underpowered on the seed dimension -- and, as noted below, they do not fold
in subsample variability either. The per-seed results are therefore reported as a
table rather than summarised into them. The `+/-` in every top-2 column above is the
standard deviation across those {len(r['experiment_seeds'])} seeds, not a confidence
interval.

| point | seed | top-2 {" | top-2 ".join(MODELS)} |
|---|---|---|---|---|
{seed_rows}

**Verdict: the gap is {headline}.**
{widening_note}
{r['delta_gap']['reading']}

## The balance-controlled control curve

Uniform {" and ".join(str(points[p]['balance']['min_class']) for p in control)} rows
per class, so balance is held FIXED at a skew of 1.0 while n moves. `game-dev`'s
{r['rarest_class_count']} labels cap uniform balance at n={points[control[-1]]['n']},
and k={points[control[0]]['balance']['min_class'] - 1} is dropped for the same
protocol-floor reason n={points[main_points[0]]['n']} is annotated -- which leaves
{len(control)} points.

{header}
{rule}
{curve_rows(control)}

{control_note}
{equal_n_note}
**This is a two-point sanity check and it is barred from carrying trend weight.** Two
points cannot distinguish a trend from a pair of draws, no CI is computed on the
difference between them, and nothing in the verdict above rests on it. It is here to
show whether the direction survives when balance is not free to move with n, and a
direction is the most it can show.

## Disclosures, counted rather than argued

**The subsample is a function of the curve point alone and does not vary with the
experiment seed.** The seeds vary the {r['curve_folds']}-fold partition and the networks'
initialisation, as in Rounds 1 and 2. They do not vary which profiles are in a point,
because "the {r['delta_gap']['n_common_profiles']} profiles common to both points" is
one set only if every seed cuts the same subsample. **The cost: every number here is
conditional on ONE subsample draw at each point**, and the intervals no more fold in
subsample sampling variability than they fold in seed variability.

**The subsample ordering has a random tie-break, and here is what it decided.**
Classes with equally many surplus rows produce identical ordering keys, so a seeded
draw and not the key decides which of their rows falls inside a point. This applies
to the {len(ties)} MAIN-curve points only: the control curve takes a prefix of each
class separately, so no two classes' rows ever compete for the same slot there.
{
  "It decided membership at " + str(len(tied_points)) + " of " + str(len(ties))
  + " points: " + "; ".join(f"n={n} ({ties[n]['rows_decided_by_tie_break']} rows contested)"
                            for n in tied_points) + "."
  if tied_points else
  "It decided nothing at any of the " + str(len(ties)) + " points: no tied key group "
  "straddles a cut, so the ordering alone fixes every point's membership."
}

**What is not measured here.** No calibration number is reported: the pre-registered
reading is about top-2 gaps, ECE is not part of it, and the Ship Floor's calibration
verdict is DEV-95's and stands unchanged. Nothing here is Qualified, Selected,
Servable or Deployable, and nothing here reopens the search budget -- **there is still
no round 3**.

## What the curve does not answer

- Circularity is untouched. More labels of the same kind would move every number here
  and none of the validity concern; a Gold Slice is what addresses that, and it does
  not exist.
- Whether Round 2's unstable selection ({r['round2_selection_note']}) is a sample-size
  effect. This curve is well placed to bear on that question and does not settle it:
  it measures how ONE frozen configuration's gap moves with n, not how the SELECTION
  moves with n, and those are different experiments.
- `MATCHER_MODEL_PATH` is untouched. That is DEV-99 and it is reserved for human
  approval.
"""


# ---------------------------------------------------------------------------- main
def _summarize(units: dict, points: list, profile_ids, labels) -> dict:
    """Everything the report reads, derived once from the fitted units.

    Recomputed by `--stage report` from the results file, so a wording change never
    silently reports one derivation while the JSON holds another.
    """
    out = {}
    for p in points:
        per_seed = units[p.label]
        ids = [profile_ids[i] for i in p.rows]
        out[p.label] = {
            "curve": p.curve,
            "n": p.n,
            "note": p.note,
            "balance": class_balance(labels, np.array(p.rows)),
            # Every value the rule produced across this point's folds and seeds --
            # usually one, because the three folds differ by at most a row. Read back
            # from what the split ACTUALLY held out, not from what was requested; the
            # two are asserted equal at fit time, and this is what makes that claim
            # checkable from the report rather than only from the code.
            "validation_size": sorted({v for s in per_seed
                                       for v in per_seed[s]["validation_sizes"]}),
            "profile_ids": ids,
            "top2_mean": {m: float(np.mean([per_seed[s][m]["top2"] for s in per_seed]))
                          for m in MODELS},
            "top2_sd": {m: float(np.std([per_seed[s][m]["top2"] for s in per_seed]))
                        for m in MODELS},
            "gaps": point_gaps(per_seed, ids),
            "per_seed": per_seed,
        }
    return out


def _analysis(points_summary: dict, digest: str, n_rows: int, labels) -> dict:
    """The pre-registered reading and everything derived from it."""
    import train_models as tm
    from env_manifest import environment_manifest

    # Derived from the points that were actually measured, not rebuilt from the
    # module constants: the label format lived in two places, and a change to
    # `curve_points` would have surfaced as a KeyError in `rebuild_report` rather than
    # as a test failure. The anchor is the smallest main point ABOVE the protocol
    # floor -- plan Step 2.6 excludes n=48 from the test -- and the far point is the
    # largest.
    main_by_n = sorted((p for p, d in points_summary.items() if d["curve"] == "main"),
                       key=lambda p: points_summary[p]["n"])
    anchor, far = main_by_n[1], main_by_n[-1]
    common = list(points_summary[anchor]["profile_ids"])
    per_comparator = delta_gap(points_summary, anchor, far, common)

    verdicts = {c: per_comparator[c]["verdict"] for c in COMPARATORS}
    if all(v == "narrowing" for v in verdicts.values()):
        reading = (
            "Read as: the neural matcher closes measurable ground on both comparators "
            "between " + anchor + " and " + far + ", so more labels of the same kind "
            "would be expected to close more. The class-balance confound qualifies "
            "that -- balance improves as n falls, so part of the small-n gap is a "
            "balance effect and the narrowing is an upper bound on the data effect."
        )
    elif any(v == "narrowing" for v in verdicts.values()):
        narrowed = [c for c, v in verdicts.items() if v == "narrowing"]
        reading = (
            "Read as: the evidence for narrowing is comparator-specific -- it holds "
            "against " + ", ".join("`" + c + "`" for c in narrowed) + " and not "
            "against the other. A one-sided result is weaker evidence that more data "
            "closes the gap than a two-sided one, because the two comparators face "
            "the same subsamples and the same folds."
        )
    else:
        reading = (
            "Read as: **at these sizes, more data of this kind is not measurably "
            "closing the gap.** That is the more actionable outcome of the two for "
            "the question this curve was funded to answer -- it is evidence against "
            "buying more labels of the same kind as a way to close the distance to "
            "the comparators, and it is NOT evidence that the gap is fixed, because "
            "an interval covering zero covers useful narrowing as well as none."
        )

    return {
        "dataset_digest": digest,
        "n_rows": n_rows,
        "experiment_seeds": list(EXPERIMENT_SEEDS),
        "class_floor": CLASS_FLOOR,
        "curve_folds": CURVE_FOLDS,
        "val_fraction": DEFAULT_VAL_FRACTION,
        "curve_inner_splits": CURVE_INNER_SPLITS,
        "gate_folds": tm.N_FOLDS,
        "gate_inner_splits": tm.INNER_SPLITS,
        "gbt_grid_size": len(tm.GBT_GRID),
        "logistic_grid_size": len(tm.LOGISTIC_C_GRID),
        "rarest_class_count": int(np.bincount(labels).min()),
        "subsample_tie_breaks": {
            str(n): v for n, v in tie_break_incidence(labels).items()
        },
        "delta_gap": {
            "small_point": anchor,
            "large_point": far,
            "n_common_profiles": len(common),
            "per_comparator": per_comparator,
            "reading": reading,
        },
        "environment": environment_manifest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _round2_selection_note() -> str:
    """Round 2's selection instability, read from its record rather than transcribed."""
    record = json.loads(ROUND2_RESULTS.read_text(encoding="utf-8"))
    counts = record["variant_selection_counts"]
    won = sum(1 for c in counts.values() if c)
    return (f"{won} Variants won contests and the top count was "
            f"{max(counts.values())} of {sum(counts.values())}")


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT.write_text(json.dumps(state), encoding="utf-8")


def run_curve() -> dict:
    """Fit every (point, seed), then derive the reading. Checkpointed per unit."""
    import train_models as tm
    from dataset_guards import dataset_digest

    variant, spec = frozen_configuration()
    df, X, y, _soft, careers, _arch, meta = tm.load_data()
    digest = dataset_digest(df, meta["feature_names"])
    profile_ids = df["profile_id"].tolist()
    n_classes = len(careers)

    points = curve_points(y)
    state = _load_checkpoint(digest)
    for point in points:
        for seed in EXPERIMENT_SEEDS:
            key = f"{point.label}|{seed}"
            if key in state["units"]:
                continue
            print(f"{point.label}, seed {seed}: {CURVE_FOLDS}-fold, "
                  f"{spec['n_members']}-member NN + nested comparators ...", flush=True)
            state["units"][key] = run_point_seed(X, y, n_classes, point, seed, variant)
            _save_checkpoint(state)

    units = {
        p.label: {str(s): state["units"][f"{p.label}|{s}"] for s in EXPERIMENT_SEEDS}
        for p in points
    }
    summary = _summarize(units, points, profile_ids, y)
    results = _analysis(summary, digest, len(df), y)
    results["points"] = summary
    results["frozen_configuration"] = {"name": variant.name, "specification": spec}
    results["round2_selection_note"] = _round2_selection_note()
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    OUT_MD.write_text(_report(results, meta), encoding="utf-8")
    print(f"wrote {OUT_MD} and {OUT_JSON}")
    return results


def rebuild_report() -> None:
    """Re-render `learning_curve.md` from `learning_curve_results.json` alone.

    Refits nothing, and reads nothing from the gitignored checkpoint -- so it works on
    any tree carrying the committed results and cannot disagree with the run that
    produced them. Every derived key is recomputed from the per-point per-seed
    indicators inside that file and written back, so the JSON and the report cannot
    end up holding two versions of one derivation.
    """
    import train_models as tm
    from dataset_guards import dataset_digest

    df, _X, y, _soft, _careers, _arch, meta = tm.load_data()
    results = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    # This stage refits nothing, but it is NOT purely a re-render: class balance and
    # the delta-gap context are recomputed from the CURRENT `y`, then written back
    # beside the OLD per-seed metrics and the old digest. Profile ids are the join
    # key, so a rebuild whose ids still line up but whose labels have moved produces
    # a report describing two different datasets at once -- and stamps it with the
    # digest of the earlier one. Nothing downstream could tell.
    digest = dataset_digest(df, meta["feature_names"])
    if digest != results.get("dataset_digest"):
        raise SystemExit(
            "learning_curve_results.json was measured on a different dataset build:\n"
            f"  results: {results.get('dataset_digest')}\n"
            f"  current: {digest}\n"
            "`--stage report` derives class balance and the delta gap from the CURRENT "
            "labels, so rebuilding now would mix them with the recorded per-seed "
            "metrics and keep the old digest. Re-measure the curve, or check out the "
            "dataset build the results were computed on."
        )

    profile_ids = df["profile_id"].tolist()
    index = {pid: i for i, pid in enumerate(profile_ids)}

    points = [
        CurvePoint(label, d["curve"], d["n"],
                   tuple(index[pid] for pid in d["profile_ids"]), d["note"])
        for label, d in results["points"].items()
    ]
    units = {p.label: results["points"][p.label]["per_seed"] for p in points}
    summary = _summarize(units, points, profile_ids, y)
    rebuilt = _analysis(summary, results["dataset_digest"], results["n_rows"], y)
    rebuilt["points"] = summary
    rebuilt["frozen_configuration"] = results["frozen_configuration"]
    rebuilt["round2_selection_note"] = _round2_selection_note()
    rebuilt["environment"] = results["environment"]
    rebuilt["created_at"] = results["created_at"]
    # The PROTOCOL the fits ran under, carried over rather than re-derived from this
    # module's constants. `--stage report` on a tree whose constants have since been
    # edited must describe the run that produced the numbers, not the code in front of
    # it -- the same reason `environment` is preserved and not recomputed.
    for key in ("curve_folds", "curve_inner_splits", "class_floor",
                "gbt_grid_size", "logistic_grid_size", "gate_folds",
                "gate_inner_splits"):
        if key in results:
            rebuilt[key] = results[key]

    OUT_JSON.write_text(json.dumps(rebuilt, indent=2), encoding="utf-8")
    OUT_MD.write_text(_report(rebuilt, meta), encoding="utf-8")
    print(f"rewrote {OUT_MD} and refreshed derived keys in {OUT_JSON} "
          "-- nothing was refitted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("curve", "report"), required=True)
    args = parser.parse_args()
    if args.stage == "report":
        rebuild_report()
    else:
        run_curve()


if __name__ == "__main__":
    main()
