"""Measures how much of a learned matcher's explainable attribution `reason_builder`
can actually phrase (DEV-89).

    cd services/matching && ../../backend/venv/Scripts/python tests/reason_diagnostics.py
    cd services/matching && ../../backend/venv/Scripts/python tests/reason_diagnostics.py --write-snapshot

Not a test: the filename sits outside pytest's `test_*` discovery because this
measures rather than asserts. What is worth *pinning* is pinned in
`test_reason_coverage.py`, which imports the functions below so the asserted number
and the recorded number are the same computation, not two implementations that agree
today. It also owns `--write-snapshot`, the only supported way to regenerate the
wording-drift snapshot that test compares against.

THE DENOMINATOR, which is the whole point of the exercise
---------------------------------------------------------
DEV-89's acceptance criterion measures against the *explainable universe*:
own-career `fit`/`sem`/`skill` plus all question features. That is deliberately
WIDER than a question-only denominator, so a question-only figure is not comparable
to this one and neither substitutes for the other -- `flip_diagnostics.py`'s
`attribution` table reports the narrow reading (0.293 on `matcher_nn_v1`) and is a
different number by design. That file did not exist on `main` when this module was
written, which is why the reference reads as a pointer rather than an assumption.
Cross-career coefficients (devops_fit pushing against frontend) are excluded from
both: they are real model behavior withheld on purpose as honest-but-unreadable, so
counting them as "lost" would charge `reason_builder` for a decision it did not make.

Four further choices, each of which moves the number, stated rather than buried.
Every one of them is COUNTED -- `measure()` returns the mass each removes, so a
reader can put it back rather than take this docstring's word for the size:

1. POSITIVE MASS ONLY. `reason_builder` renders a feature only above
   MIN_CONTRIBUTION, so negative attribution is unrenderable for every feature in
   the bank or out of it. Counting it would inflate the gap.

2. RENDERABLE MEANS "HAS A RENDERING PATH", not "survives into the final list".
   `build_reasons` caps output at MAX_REASONS with at most MAX_QUESTION_REASONS
   question sentences, so at most 2 of up to 18 eligible questions are ever
   printed. Under a "survives" reading the >= 0.99 bar would be unreachable by
   construction and the criterion meaningless. The defect DEV-89 fixed is that
   q11-q18 never entered the ranking at all; the cap is a presentation budget
   applied afterwards to features that did.

   Renderability is DETERMINED BY PROBING `build_reasons` itself (see
   `probe_renderable`), not by testing membership of `QUESTION_PHRASES`. Reading
   the mapping would make the ratio 1.000 by construction the moment coverage
   holds, and would miss every other way the function can drop a unit -- a
   `questions_by_id` miss, or an answer outside `0 <= val < len(options)`. The
   probe drives the real code path, so those count as unrenderable too.

3. ANSWERED QUESTIONS ONLY. A question the user never saw has no chosen option to
   quote -- "You chose ..." cannot be written -- so `build_reasons` gates on
   `answers.get(qid) is not None`, correctly. Its features still carry attribution
   (an unanswered question standardizes to a non-zero value), so counting them
   would charge the phrase mapping for missing input rather than missing coverage.
   Counted as `unanswered_share`.

4. THE `skill` SIGNAL NEEDS NAMES TO LIST. `build_reasons` writes its skill
   sentence only with a non-empty `matched_skills`, so with none there is no
   rendering path and the unit is dropped from the universe rather than counted as
   lost. This one shrinks the PRE-DEV-89 counterfactual's denominator too, which
   flatters the "before" gap the vacuity test leans on -- so it is counted as
   `skill_dropped_share` and printed, not merely argued.

DISCLOSURE. `chromadb` is not installed in `backend/venv`, so the real RAG store
cannot be driven from here and `semantic_similarity` is canned (same constraint
DEV-99 disclosed). Two consequences, both counted below rather than argued:

  - Market skills are given to EVERY career, not just the two the shared
    `conftest.make_candidates()` fixture covers. Without this the `<career>_skill`
    sentence is dead for 14 of 16 careers -- `build_reasons` needs a non-empty
    `matched_skills` to write it -- and the ratio would fall for a reason that has
    nothing to do with phrase coverage. `--fixture conftest` runs the sparse
    fixture instead so the size of this thumb is visible.
  - Answer sets are drawn under a fixed seed, honoring each question's `show_if`
    so q14-q17 appear exactly one per respondent, as in serving. `--seeds` re-runs
    under further seeds so the spread is visible rather than promised.

Feature vectors are never synthetic: `feature_builder` builds them from the real
career catalog and question bank, so the input layout is the serving one.
"""
import argparse
import contextlib
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

_SERVICE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_SERVICE.parent), str(_SERVICE)]

from app.repositories.career_repository import CareerCandidate  # noqa: E402
from app.services import reason_builder  # noqa: E402
from app.services import feature_builder  # noqa: E402
from app.services.matcher import Matcher, load_matcher  # noqa: E402
from app.services.matching_service import TOP_N, _skill_signals  # noqa: E402
from app.services.reason_builder import MIN_CONTRIBUTION, build_reasons  # noqa: E402
from common.data import load_careers, load_questions  # noqa: E402

REPO_ROOT = _SERVICE.parents[1]
DEFAULT_ARTIFACT = REPO_ROOT / "data" / "models" / "matcher_logistic_v2.json"
SNAPSHOT = Path(__file__).parent / "data" / "question_phrases_snapshot.json"

QUESTIONS = load_questions()
QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}
QIDS = [q["id"] for q in QUESTIONS]
# The three own-career signals reason_builder.py:57-66 emits sentences for.
SIGNALS = ("fit", "sem", "skill")

# DEV-89's acceptance bar. Defined HERE, beside the computation, so the assertion in
# test_reason_coverage.py and the `< bar` tally inside measure() cannot drift apart.
MASS_BAR = 0.99

# Fixed so the record's numbers are reproducible rather than merely representative.
SEED = 20260803
ANSWER_SETS = 200
SENSITIVITY_SEEDS = (1, 2, 3, 4)

# What the phrase mapping covered before DEV-89 -- used to show the metric is not
# vacuous, i.e. that it would have failed on the code this ticket replaced. The one
# place a q1..qN literal is justified: a historical mapping cannot be derived from
# today's questions.json, which is the very thing that changed.
PRE_DEV89_PHRASED = frozenset(f"q{i}" for i in range(1, 11))


def answer_sets(n: int, seed: int = SEED, honor_show_if: bool = True) -> list[dict]:
    """Random respondents. With `honor_show_if`, a gated question is answered only
    when its trigger fired -- so exactly one of q14-q17 is answered per respondent,
    which is what the serving path actually produces."""
    rng = random.Random(seed)
    sets = []
    for _ in range(n):
        answers: dict[str, int | None] = {}
        for q in QUESTIONS:
            gate = q.get("show_if")
            if honor_show_if and gate and answers.get(gate["q"]) not in gate["in"]:
                answers[q["id"]] = None
                continue
            answers[q["id"]] = rng.randrange(len(q["options"]))
        sets.append(answers)
    return sets


def candidates(skill_rich: bool = True) -> list[CareerCandidate]:
    """One candidate per real career. `skill_rich` gives every career market demand
    for its own key skills, so the `<career>_skill` sentence has a live rendering
    path everywhere; see the disclosure in the module docstring."""
    from tests.conftest import make_candidates

    base = make_candidates()
    if not skill_rich:
        return base
    return [
        CareerCandidate(
            career=c.career,
            semantic_similarity=c.semantic_similarity,
            market_skills=c.market_skills
            or Counter({s.lower(): 3 for s in c.career["keySkills"]}),
        )
        for c in base
    ]


@contextlib.contextmanager
def phrase_mapping(phrased: frozenset[str] | None):
    """Temporarily restrict `QUESTION_PHRASES` to `phrased`, then restore it.

    The counterfactual has to be built by mutating the real dict rather than by
    passing a set around, because that dict is ALSO `build_reasons`' iteration set --
    which is the whole defect. Restricting it reconstructs the pre-DEV-89 behavior
    exactly, dropped attribution included, instead of approximating it.
    """
    if phrased is None:
        yield
        return
    original = dict(reason_builder.QUESTION_PHRASES)
    try:
        reason_builder.QUESTION_PHRASES.clear()
        reason_builder.QUESTION_PHRASES.update(
            {k: v for k, v in original.items() if k in phrased}
        )
        yield
    finally:
        reason_builder.QUESTION_PHRASES.clear()
        reason_builder.QUESTION_PHRASES.update(original)


def probe_renderable(career: dict) -> frozenset[str]:
    """Which units `build_reasons` can actually turn into a sentence, found by
    DRIVING IT rather than by reading `QUESTION_PHRASES` (choice 2 above).

    One probe per unit, with attribution parked on that unit alone so the
    MAX_REASONS / MAX_QUESTION_REASONS budget can never be the reason a sentence is
    absent. A unit counts as renderable only if the output actually mentions it.
    """
    mass = MIN_CONTRIBUTION + 1.0
    out: set[str] = set()

    for qid in QIDS:
        options = QUESTIONS_BY_ID[qid]["options"]
        reasons = build_reasons(
            career, {qid: 0}, {qid: mass}, [], QUESTIONS_BY_ID,
        )
        if any(options[0] in r for r in reasons):
            out.add(qid)

    probes = {
        "fit": ([], False),
        "sem": ([], False),
        # The skill sentence is the one that needs names to list (choice 4).
        "skill": (["React"], False),
    }
    for signal, (matched, user_skills) in probes.items():
        baseline = build_reasons(career, {}, {}, matched, QUESTIONS_BY_ID, user_skills)
        reasons = build_reasons(
            career, {}, {f"{career['id']}_{signal}": mass}, matched,
            QUESTIONS_BY_ID, user_skills,
        )
        if set(reasons) - set(baseline):
            out.add(signal)
    return frozenset(out)


def explainable_units(
    contributions: dict[str, float],
    career_id: str,
    answers: dict[str, int | None],
    matched_skills: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    """The explainable universe for one (respondent, career) explanation.

    Returns `(units, excluded)`. `units` maps a unit name to its positive
    attribution mass; `excluded` maps each documented exclusion to the mass it
    removed, so the choices above are counted rather than asserted. A question is
    one unit (ordinal + presence mask combined, exactly as `build_reasons` scores
    it); each own-career signal is one.
    """
    units: dict[str, float] = {}
    excluded = {"unanswered": 0.0, "skill_no_names": 0.0}
    for qid in QIDS:
        total = contributions.get(qid, 0.0) + contributions.get(f"{qid}_present", 0.0)
        if total <= MIN_CONTRIBUTION:
            continue
        if answers.get(qid) is None:
            excluded["unanswered"] += total
        else:
            units[qid] = total
    for signal in SIGNALS:
        value = contributions.get(f"{career_id}_{signal}", 0.0)
        if value <= MIN_CONTRIBUTION:
            continue
        # The skill sentence needs names to list; without them there is no path.
        if signal == "skill" and not matched_skills:
            excluded["skill_no_names"] += value
            continue
        units[signal] = value
    return units, excluded


def renderable_share(units: dict[str, float], renderable: frozenset[str]) -> float | None:
    """Share of explainable mass `reason_builder` has a rendering path for.

    `None` when the explanation carried no explainable mass at all, which is a
    distinct outcome from a share of 0.0 and is counted separately.
    """
    total = sum(units.values())
    if not total:
        return None
    return sum(m for name, m in units.items() if name in renderable) / total


def measure(
    model: Matcher,
    cands: list[CareerCandidate],
    sets: list[dict],
    phrased: frozenset[str] | None = None,
    bar: float = MASS_BAR,
) -> dict:
    """Renderable share over `sets` x the top TOP_N careers of each.

    `phrased` restricts the phrase mapping for the duration of the run; `None` means
    "measure the mapping as it actually is". It is resolved HERE rather than as a
    default argument value, because a default evaluated at import would freeze the
    mapping as it was then -- precisely the class of staleness this module detects.

    The renderable set is PROBED from `build_reasons` under that same restriction,
    so it reflects what the function does rather than what the dict contains.
    """
    careers = [c.career for c in cands]
    semantic = {c.career["id"]: c.semantic_similarity for c in cands}
    market = {c.career["id"]: c.market_skills for c in cands}
    by_id = {c.career["id"]: c for c in cands}

    shares: list[float] = []
    excluded_shares: dict[str, list[float]] = {"unanswered": [], "skill_no_names": []}
    blank = 0
    with phrase_mapping(phrased):
        renderable = {c["id"]: probe_renderable(c) for c in careers}
        for answers in sets:
            vector = feature_builder.build_feature_vector(
                answers, careers, semantic, market
            )
            probs = model.predict_proba(vector)
            for cid in sorted(probs, key=lambda c: (-probs[c], c))[:TOP_N]:
                _, matched, _ = _skill_signals(by_id[cid].career, by_id[cid])
                contrib = model.contributions(vector, cid)
                units, excluded = explainable_units(contrib, cid, answers, matched)
                share = renderable_share(units, renderable[cid])
                if share is None:
                    blank += 1
                    continue
                shares.append(share)
                universe = sum(units.values()) + sum(excluded.values())
                for name, mass in excluded.items():
                    excluded_shares[name].append(mass / universe)
    return {
        "explanations": len(shares) + blank,
        "blank": blank,
        "shares": shares,
        "mean": statistics.mean(shares) if shares else 0.0,
        "min": min(shares) if shares else 0.0,
        "bar": bar,
        "below_bar": sum(1 for s in shares if s < bar),
        "unanswered_share": (
            statistics.mean(excluded_shares["unanswered"]) if shares else 0.0
        ),
        "skill_dropped_share": (
            statistics.mean(excluded_shares["skill_no_names"]) if shares else 0.0
        ),
    }


# ------------------------------------------------------------------ reporting
def _row(label: str, stats: dict) -> str:
    return (
        f"{label:<34}{stats['mean']:>9.3f}{stats['min']:>9.3f}"
        f"{stats['below_bar']:>10}{stats['explanations']:>9}"
    )


def report(artifact: Path, skill_rich: bool, with_seeds: bool) -> None:
    model = load_matcher(artifact)
    cands = candidates(skill_rich=skill_rich)
    sets = answer_sets(ANSWER_SETS)
    phrases = reason_builder.QUESTION_PHRASES
    missing = [q for q in QIDS if q not in phrases]

    print(f"\nartifact {artifact.name}, {ANSWER_SETS} answer sets x top-{TOP_N}, seed {SEED}")
    print(f"fixture: {'skill-rich' if skill_rich else 'conftest (sparse market skills)'}")
    print(f"bank {len(QIDS)} questions, phrased {len(phrases)}, missing {missing or 'none'}")

    print("\n=== renderable share of explainable attribution mass ===")
    print(f"{'phrase mapping':<34}{'mean':>9}{'min':>9}{'< 0.99':>10}{'expl':>9}")
    now = measure(model, cands, sets)
    print(_row("current (q1-q18)", now))
    before = measure(model, cands, sets, phrased=PRE_DEV89_PHRASED)
    print(_row("pre-DEV-89 (q1-q10)", before))
    print("\nexcluded from the universe (choices 3 and 4), mean share of it:")
    print(f"  unanswered questions      {now['unanswered_share']:.3f}")
    print(f"  skill signal, no names    {now['skill_dropped_share']:.3f}")
    print(f"    same, pre-DEV-89        {before['skill_dropped_share']:.3f}")
    print(f"blank explanations (no explainable mass): {now['blank']}")

    all_answered = measure(model, cands, answer_sets(ANSWER_SETS, honor_show_if=False))
    print("\n=== same, ignoring show_if (all 18 answered) ===")
    print(_row("current (q1-q18)", all_answered))

    if with_seeds:
        print(f"\n=== seed sensitivity, {ANSWER_SETS} answer sets per seed ===")
        print(f"{'seed':>12}{'current':>10}{'pre-DEV-89':>13}")
        for seed in SENSITIVITY_SEEDS:
            s = answer_sets(ANSWER_SETS, seed=seed)
            print(
                f"{seed:>12}{measure(model, cands, s)['mean']:>10.3f}"
                f"{measure(model, cands, s, phrased=PRE_DEV89_PHRASED)['mean']:>13.3f}"
            )


def write_snapshot() -> None:
    """Regenerate the wording-drift snapshot `test_reason_coverage.py` compares to.

    Deliberately a separate, explicit invocation rather than an auto-heal on test
    failure: the point of that test is to make a human re-read the phrase against the
    new wording, and a snapshot that rewrites itself would defeat it. Run this only
    AFTER that re-read.
    """
    payload = [
        {
            "id": q["id"],
            "phrase": reason_builder.QUESTION_PHRASES.get(q["id"]),
            "text": q["text"],
            "options": q["options"],
        }
        for q in QUESTIONS
    ]
    # ensure_ascii so the file stays pure ASCII: the bank uses characters (U+2026
    # and curly quotes) a cp1252 console cannot print, and this file gets opened and
    # diffed by humans on exactly such consoles.
    SNAPSHOT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {SNAPSHOT.relative_to(_SERVICE)} ({len(payload)} questions)")
    print("re-read each phrase against the new wording before committing this.")


def main() -> None:
    parser = argparse.ArgumentParser(description="DEV-89 renderable-attribution table")
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--fixture", choices=("skill-rich", "conftest"), default="skill-rich")
    parser.add_argument("--seeds", action="store_true", help="add the seed-sensitivity table")
    parser.add_argument(
        "--write-snapshot",
        action="store_true",
        help="regenerate the wording-drift snapshot instead of measuring",
    )
    args = parser.parse_args()
    if args.write_snapshot:
        write_snapshot()
        return
    report(args.artifact, args.fixture == "skill-rich", args.seeds)


if __name__ == "__main__":
    main()
