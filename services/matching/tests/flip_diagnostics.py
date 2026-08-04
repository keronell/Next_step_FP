"""Regenerates the two measurement tables in the DEV-99 reproduction record.

    cd services/matching && ../../backend/venv/Scripts/python tests/flip_diagnostics.py

Not a test — same convention as `ig_diagnostics.py`: the filename sits outside
pytest's `test_*` discovery because this measures rather than asserts. What is worth
*pinning* is pinned in `test_flip_readiness.py`; this produces the numbers the record
quotes, so a reader can re-derive them instead of trusting a literal.

Two questions, deliberately in one script because both size the same decision:

1. `percent-scale` — for the SAME request, what `matchPercent` does each scorer put on
   screen? This sizes what ADR 0005's mitigation substitutes (built 2026-08-04).
2. `attribution` — of the positive question-feature attribution `matcher_nn_v1`
   actually produces, what share can `reason_builder` phrase? This sizes DEV-89 on the
   artifact that would ship, rather than by feature count.

DISCLOSURE, which applies to both: candidates come from `tests/conftest`'s
`make_candidates()`, whose `semantic_similarity` and `market_skills` are canned —
`chromadb` is not installed in `backend/venv`, so the real RAG store cannot be driven
from here. Question-feature attributions are the model's own and do not depend on
those values except through *which* careers land in the top 3; the percentage table is
a property of the scorers' output scales. Ranking-agreement rates between scorers ARE
fixture-dependent, so this script does not report them and the record does not quote
them.

The feature vectors are never synthetic — `feature_builder` builds them from the real
career catalog and question bank, so the input distribution is the serving one.
"""
import argparse
import random
import statistics
import sys
from pathlib import Path

_SERVICE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_SERVICE.parent), str(_SERVICE)]

from app.services import feature_builder  # noqa: E402
from app.services.matcher import load_matcher  # noqa: E402
from app.services.matching_service import match  # noqa: E402
from app.services.reason_builder import MIN_CONTRIBUTION, QUESTION_PHRASES  # noqa: E402
from common.data import load_questions  # noqa: E402

from tests.conftest import make_candidates  # noqa: E402

REPO_ROOT = _SERVICE.parents[1]
MODELS = REPO_ROOT / "data" / "models"
QIDS = [q["id"] for q in load_questions()]
RENDERABLE = set(QUESTION_PHRASES)
# Fixed so the record's numbers are reproducible rather than merely representative.
SEED = 20260803
ANSWER_SETS = 200
ATTRIBUTION_SETS = 100  # x3 explained careers each
# Four further draws, for the counted fixture disclosure in seed_sensitivity().
SENSITIVITY_SEEDS = (1, 2, 3, 4)
SENSITIVITY_SETS = 200


def answer_sets(n: int) -> list[dict]:
    rng = random.Random(SEED)
    return [{q: rng.randint(0, 3) for q in QIDS} for _ in range(n)]


def percent_scale(n: int) -> None:
    """Top-1 matchPercent under each scorer, same requests."""
    print(f"\n=== displayed top-1 matchPercent, {n} answer sets, seed {SEED} ===")
    print(f"{'scorer':<38}{'mean':>8}{'min':>6}{'max':>6}")
    cands = make_candidates()
    sets = answer_sets(n)

    rows = [("formula (ADR 0005 says display this)", None)]
    for name in ("matcher_logistic_v2", "matcher_nn_v1"):
        path = MODELS / f"{name}.json"
        if path.exists():
            rows.append((name, load_matcher(path)))
        else:
            print(f"  (skipped {name}: artifact not present)")

    for label, model in rows:
        tops = [match(a, cands, model=model)[0]["matchPercent"] for a in sets]
        print(f"{label:<38}{statistics.mean(tops):>8.1f}{min(tops):>6}{max(tops):>6}")


def attribution(n: int) -> None:
    """Share of positive question-feature attribution reason_builder can phrase.

    Only POSITIVE mass counts: `reason_builder` renders a question only when its
    combined contribution exceeds MIN_CONTRIBUTION, so negative attribution is
    unrenderable for every question in the bank or out of it. Counting it would
    inflate the gap.
    """
    path = MODELS / "matcher_nn_v1.json"
    if not path.exists():
        print("\n(skipped attribution: matcher_nn_v1.json not present)")
        return
    model = load_matcher(path)
    cands = make_candidates()
    careers = [c.career for c in cands]
    semantic = {c.career["id"]: c.semantic_similarity for c in cands}
    market = {c.career["id"]: c.market_skills for c in cands}

    shares, blank, explained = [], 0, 0
    for answers in answer_sets(n):
        vector = feature_builder.build_feature_vector(answers, careers, semantic, market)
        probs = model.predict_proba(vector)
        for cid in sorted(probs, key=lambda c: (-probs[c], c))[:3]:
            explained += 1
            contrib = model.contributions(vector, cid)
            positive = {}
            for qid in QIDS:
                total = contrib.get(qid, 0.0) + contrib.get(f"{qid}_present", 0.0)
                if total > MIN_CONTRIBUTION:
                    positive[qid] = total
            if not positive:
                blank += 1
                continue
            shares.append(
                sum(v for q, v in positive.items() if q in RENDERABLE) / sum(positive.values())
            )

    missing = [q for q in QIDS if q not in RENDERABLE]
    print(f"\n=== reason_builder coverage on matcher_nn_v1, {explained} explanations ===")
    print(f"  bank {len(QIDS)} questions, phrased {len(RENDERABLE)}, missing {missing}")
    print(f"  by feature COUNT   : {len(missing) * 2} of {len(QIDS) * 2} discarded "
          f"({len(missing) / len(QIDS):.1%})")
    if not shares:
        print("  no explanation carried positive question mass")
        return
    mean = statistics.mean(shares)
    below = sum(1 for s in shares if s < 0.5)
    print(f"  explanations with positive question mass: {len(shares)} (blank: {blank})")
    print(f"  by attribution MASS: renderable mean {mean:.3f}, median "
          f"{statistics.median(shares):.3f}")
    print(f"                       DISCARDED mean {1 - mean:.3f}")
    print(f"  majority of question mass discarded: {below}/{len(shares)} "
          f"({below / len(shares):.1%})")


def seed_sensitivity() -> None:
    """The counted form of this script's fixture disclosure.

    Arguing "the fixture is harmless because the tables measure output scales" is not
    evidence. This re-runs the percentage table under four further seeds and prints the
    spread, so a reader can see how much of the headline gap is the draw. The seeds
    vary only the ANSWER SETS -- the canned RAG signals are the same throughout, which
    is the part that cannot be varied from `backend/venv` and stays a disclosure rather
    than a measurement.
    """
    path = MODELS / "matcher_nn_v1.json"
    if not path.exists():
        print("\n(skipped seed sensitivity: matcher_nn_v1.json not present)")
        return
    model = load_matcher(path)
    cands = make_candidates()
    print(f"\n=== seed sensitivity of the gap, {SENSITIVITY_SETS} answer sets per seed ===")
    print(f"{'seed':>12}{'formula':>10}{'nn':>8}{'gap':>8}")
    gaps = []
    for seed in SENSITIVITY_SEEDS:
        rng = random.Random(seed)
        sets = [{q: rng.randint(0, 3) for q in QIDS} for _ in range(SENSITIVITY_SETS)]
        f = statistics.mean(match(a, cands)[0]["matchPercent"] for a in sets)
        n = statistics.mean(match(a, cands, model=model)[0]["matchPercent"] for a in sets)
        gaps.append(f - n)
        print(f"{seed:>12}{f:>10.1f}{n:>8.1f}{f - n:>8.1f}")
    print(f"  gap across seeds: mean {statistics.mean(gaps):.1f} pts, "
          f"min {min(gaps):.1f}, max {max(gaps):.1f}")


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()  # --help only
    percent_scale(ANSWER_SETS)
    attribution(ATTRIBUTION_SETS)
    seed_sensitivity()


if __name__ == "__main__":
    main()
