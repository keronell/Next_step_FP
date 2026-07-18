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
