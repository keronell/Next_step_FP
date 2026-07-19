"""Shared fail-fast guards for the training pipeline (Phases 1-3).

The stratified 5-fold protocol in evaluate_matchers.py / train_models.py needs at
least N_FOLDS members of every class; below that, folds lose classes and the OOF
probability matrices / NN validation splits break in confusing ways deep into a
run. Phase 1-3 entry points call assert_min_class_coverage() up front so a
label-starved dataset (Gate 0 not satisfied) fails immediately with the exact
shortfall instead.
"""
from collections import Counter

# Floor for stratified 5-fold CV (each class must appear in every fold's training
# partition). Nested CV and the NN's inner validation split want more than this —
# treat 5 as the hard minimum, not a target.
MIN_LABELS_PER_CAREER = 5


def assert_min_class_coverage(labels, career_ids, minimum: int = MIN_LABELS_PER_CAREER,
                              context: str = "") -> None:
    """Exit with the per-career shortfall when any catalog career has fewer than
    `minimum` labels. `labels` is any iterable of label_top1 values; `career_ids`
    is the full catalog (a career with zero labels must fail too)."""
    counts = Counter(labels)
    shortfall = {
        cid: counts.get(cid, 0)
        for cid in career_ids
        if counts.get(cid, 0) < minimum
    }
    if shortfall:
        where = f" ({context})" if context else ""
        raise SystemExit(
            f"Minimum-class coverage guard failed{where}: stratified {minimum}-fold "
            f"CV needs >= {minimum} labels per career, short: {shortfall}. "
            "Gate 0 is not satisfied — fix Phase-0 labeling coverage for these "
            "careers before running Phases 1-3."
        )


def dataset_digest(df, feature_names) -> str:
    """Order-independent sha256 digest of the evaluated content (features + labels
    + profile ids). Provenance files (gate1_verdict.json, gate2_winner.json) store
    it and downstream phases verify it against the data they actually loaded —
    sidecar metadata (created_at / n_rows) cannot detect a replaced or edited
    feature table whose row count happens to match."""
    import hashlib

    import pandas as pd

    cols = (
        df[[*feature_names, "label_top1", "profile_id"]]
        .sort_values("profile_id")
        .reset_index(drop=True)
    )
    row_hashes = pd.util.hash_pandas_object(cols, index=False).to_numpy()
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


def dataset_caveats(labels, career_ids, minimum: int = MIN_LABELS_PER_CAREER) -> list[str]:
    """Class-balance caveats derived from the labels themselves, shared by the
    evaluation report and the exported artifact so both always describe the
    dataset actually loaded (never a previous run's counts). Empty when neither
    condition holds."""
    counts = Counter(labels)
    n = sum(counts.values())
    floor = [f"{cid} ({counts.get(cid, 0)} labels)" for cid in career_ids
             if counts.get(cid, 0) <= minimum]
    over = [f"{cid} ({counts[cid]}/{n} rows, {counts[cid] / n:.0%})" for cid in career_ids
            if counts.get(cid, 0) / n > 2.0 / len(career_ids)]
    caveats = []
    if floor:
        caveats.append(
            f"Floor-level class representation for {', '.join(sorted(floor))} — at or "
            f"below the {minimum}-label stratified-CV minimum; treat their predictions "
            "and metrics as low-confidence."
        )
    if over:
        caveats.append(
            f"Over-represented classes: {', '.join(sorted(over))} (more than 2x the "
            "uniform share). class_weight='balanced' prevents amplification during "
            "training, but the label skew remains in the data."
        )
    return caveats
