"""Regenerates the completeness table in the DEV-94 reproduction record.

    cd services/matching && ../../backend/venv/Scripts/python tests/ig_diagnostics.py

Not a test — the filename is deliberately outside pytest's `test_*` discovery, since
this measures rather than asserts. The two properties worth *pinning* are pinned in
`test_matcher_nn.py`; this is the thing that produces the numbers the record quotes,
so a reader can re-derive them instead of trusting them.

The artifact is **synthetic**: pseudo-random weights at the shipped trunk shape,
because no trained neural artifact exists until DEV-97. The feature vectors are not
synthetic — `feature_builder` builds them from the real career catalog and question
bank, so the input distribution is the serving one. `--weight-scale` exists because
the fall-through rate is sensitive to how large the random weights are, and a report
that quoted one scale without saying so would be hiding its own thumb on the scale.
"""
import argparse
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

_SERVICE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_SERVICE.parent), str(_SERVICE)]

from app.services import feature_builder  # noqa: E402
from app.services.matcher_nn import NeuralMatcher  # noqa: E402
from common.data import load_careers, load_questions  # noqa: E402

from tests.conftest import nn_artifact  # noqa: E402

CAREERS = load_careers()
QUESTIONS = load_questions()
NAMES = feature_builder.feature_names(CAREERS)
CIDS = [c["id"] for c in CAREERS]
SEED = 7
PROFILE_SEED = 20260731


def member(shapes, seed: int, scale: float) -> dict:
    rng = random.Random(seed)
    return {
        "layers": [
            {
                "weight": [[rng.uniform(-scale, scale) for _ in range(n_in)]
                           for _ in range(n_out)],
                "bias": [rng.uniform(-0.5, 0.5) for _ in range(n_out)],
            }
            for n_out, n_in in shapes
        ]
    }


def shipped_shape_artifact(n_members: int, hidden, weight_scale: float) -> dict:
    shapes, prev = [], len(NAMES)
    for width in hidden:
        shapes.append((width, prev))
        prev = width
    shapes.append((len(CIDS), prev))
    return nn_artifact(
        NAMES, CIDS,
        [member(shapes, SEED + i, weight_scale) for i in range(n_members)],
    )


def realistic_vector(rng: random.Random) -> list[float]:
    """A feature vector the serving path could actually produce: real question ids,
    real careers, ~15% of questions unanswered as the branching bank allows."""
    answers = {q["id"]: (rng.choice([0, 1, 2, 3]) if rng.random() > 0.15 else None)
               for q in QUESTIONS}
    semantic = {c["id"]: rng.uniform(0.1, 0.9) for c in CAREERS}
    market = {c["id"]: Counter({s.lower(): 3 for s in c["keySkills"][: rng.randint(0, 4)]})
              for c in CAREERS}
    return feature_builder.build_feature_vector(answers, CAREERS, semantic, market)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=int, default=40)
    parser.add_argument("--members", type=int, default=5)
    parser.add_argument("--weight-scale", type=float, default=1.0)
    args = parser.parse_args()

    matcher = NeuralMatcher(
        shipped_shape_artifact(args.members, (64, 32), args.weight_scale)
    )
    rng = random.Random(PROFILE_SEED)
    vectors = [realistic_vector(rng) for _ in range(args.profiles)]

    steps: Counter = Counter()
    strict, lenient, absolute = [], [], []
    failed = 0
    for vector in vectors:
        # Every career, not just the served top 3, so the table is not flattered by
        # looking only at the careers the model is most confident about.
        for cid in matcher.careers:
            result = matcher.explain(vector, cid)
            steps[result.steps] += 1
            strict.append(result.residual)
            lenient.append(result.absolute_residual / result.attribution_mass)
            absolute.append(result.absolute_residual)
            failed += not result.converged

    total = len(vectors) * len(matcher.careers)
    print(f"artifact: {args.members} members, trunk {len(NAMES)} -> 64 -> 32 -> "
          f"{len(CIDS)}, weights uniform(+/-{args.weight_scale}), seed {SEED}")
    print(f"profiles={len(vectors)}  careers={len(matcher.careers)}  explanations={total}")
    print("step counts reached:", dict(sorted(steps.items())))
    print(f"fell through (no model reasons): {failed}/{total} = {failed / total:.1%}")
    for label, xs in (("strict   resid / abs(delta)", strict),
                      ("lenient  resid / sum(abs(a))", lenient),
                      ("absolute residual          ", absolute)):
        p90 = statistics.quantiles(xs, n=100)[89]
        print(f"  {label}: median {statistics.median(xs):.3g}  p90 {p90:.3g}  "
              f"max {max(xs):.3g}")


if __name__ == "__main__":
    main()
