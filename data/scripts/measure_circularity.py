"""Measure how circular the silver labels are with the careers.json answer key.

Every report in this tree carries the claim that the panel's stage-2 vote "follows
the answer key derived from careers.json bonuses ~94% of the time it speaks", and
both exported artifacts carry it inside `caveats` where it reaches the
recommendations response. Until DEV-98 that figure was a literal: no script
computed it, unlike the 52.2% formula-vs-panel number `panel_label_profiles.py`
writes into `synthetic_agreement_report.md`. This computes it, from the raw vote
log, so the claim fails loudly instead of quietly ageing if the labels are ever
regenerated.

The stage-1 shortlist and the option->career key are imported from
`panel_label_profiles` rather than reimplemented -- a reimplementation would
compare two copies of the same logic and agree while proving nothing.

    data/venv-training/Scripts/python data/scripts/measure_circularity.py
    data/venv-training/Scripts/python data/scripts/measure_circularity.py --json

Four readings are reported because they answer different questions and only one of
them is the quoted claim -- shortlist containment in particular is structural rather
than evidence. See `docs/dev-23-nn-decision.md`, "Validity", for what each is for.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.machinery
import json
import sys
import types
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

# `panel_label_profiles` imports `requests`/`tqdm` for the Ollama call. Nothing
# reached from here touches either, and the hash-pinned training venv has neither
# and must not gain them (the dataset digest depends on that venv -- see
# "Matcher training environment" in README.md). The imported code is
# byte-identical; only two unexercised network/UI dependencies are stubbed, the
# same disclosed shim `tests/test_export_nn_model.py` uses for `common.config`.
#
# Two things this shim must get right, both found by running the full suite rather
# than this module alone. It is inserted into PROCESS-GLOBAL `sys.modules`, so:
#   - it stubs only what genuinely fails to import, never shadowing a real package;
#   - each stub carries a real `ModuleSpec`. torch's deterministic-fit context calls
#     `importlib.util.find_spec`, which walks `sys.modules` and raises
#     `ValueError: <name>.__spec__ is None` on a bare `ModuleType`. A `__spec__`-less
#     stub therefore breaks every torch test in the suite that imports this one.
for _name in ("requests", "tqdm"):
    try:
        importlib.import_module(_name)
    except ImportError:
        _stub = types.ModuleType(_name)
        _stub.__spec__ = importlib.machinery.ModuleSpec(_name, loader=None)
        _stub.tqdm = lambda iterable, **kwargs: iterable
        sys.modules[_name] = _stub

sys.path.insert(0, str(Path(__file__).resolve().parent))

import panel_label_profiles as panel  # noqa: E402

VOTE_LOG = Path("data/training/panel_votes.jsonl")


@dataclass
class Tally:
    """How often one population of choices lands where the answer key points.

    A choice is a career picked for a profile -- a persona's stage-2 `top1`, or the
    consensus label those votes produce. Both populations are counted the same way,
    which is the whole reason this is one type and not two sets of loop variables.
    """

    #: choices whose profile reached stage 2 at all (q2 answered, so a shortlist exists)
    considered: int = 0
    #: of those, choices lying inside the deterministic stage-1 shortlist
    in_shortlist: int = 0
    #: of those, choices where at least one tie-breaker was answered -- the key "speaks"
    key_speaks: int = 0
    #: of the speaking ones, choices the key points at under ANY bonus rule
    follows: int = 0
    #: the same under primary (+3) rules only -- the strict reading
    follows_primary: int = 0

    @property
    def shortlist_containment(self) -> float:
        return self.in_shortlist / self.considered

    @property
    def follow_rate(self) -> float:
        return self.follows / self.key_speaks

    @property
    def follow_rate_primary(self) -> float:
        return self.follows_primary / self.key_speaks


@dataclass
class Measurement:
    prompt_version: str
    votes: int
    profiles: int
    silver_profiles: int
    #: one row per persona vote -- the population the "~94%" claim is about
    vote_level: Tally
    #: one row per silver label -- the population models actually train on
    label_level: Tally


def load_votes(path: Path = VOTE_LOG) -> list[dict]:
    """Error-free votes at the prompt version that produced the shipped labels."""
    with path.open(encoding="utf-8") as handle:
        return [
            vote for vote in map(json.loads, handle)
            if vote.get("prompt_version") == panel.PROMPT_VERSION and not vote.get("error")
        ]


def consensus_labels(votes: list[dict]) -> dict[str, str]:
    """Reproduce the >= 2/3 top-1 consensus filter that built silver_labels.

    Recomputed rather than read from the parquet so this script needs no pyarrow,
    and so a mismatch against the recorded 232 is visible as a failure here.
    """
    by_profile: dict[str, list[dict]] = {}
    for vote in votes:
        by_profile.setdefault(vote["profile_id"], []).append(vote)
    labels = {}
    for profile_id, profile_votes in by_profile.items():
        if len(profile_votes) < 3:
            continue
        career, count = Counter(v["top1"] for v in profile_votes).most_common(1)[0]
        if count >= 2:
            labels[profile_id] = career
    return labels


def key_targets(answers: dict, shortlist: list[dict]) -> tuple[set[str], set[str]]:
    """Careers the answered tie-breakers point to: (any bonus, primary >= +3 only).

    The tie-breakers are exactly the ones stage 2 renders -- the q2-gated family
    question plus the linear discriminators -- so this reads the same key the
    panel was shown.
    """
    any_bonus: set[str] = set()
    primary: set[str] = set()
    for qid in [panel.GATED_BY_Q2[answers["q2"]], *panel.LINEAR_DISCRIMINATORS]:
        chosen = answers.get(qid)
        if chosen is None:
            continue
        chosen = int(chosen)
        any_bonus |= set(panel._bonus_key(shortlist, qid).get(chosen, []))
        primary |= {
            career["id"] for career in shortlist for rule in career["bonuses"]
            if rule["qId"] == qid and rule["answerValue"] == chosen and rule["bonus"] >= 3
        }
    return any_bonus, primary


def tally(choices: Iterable[tuple[dict, str]]) -> Tally:
    """Count one population of (answers, chosen career) pairs against the key.

    Both readings run through here, so the vote-level and label-level numbers cannot
    drift apart by one of them acquiring a filter the other lacks.
    """
    careers = panel._CAREER_CATALOG
    by_id = {career["id"]: career for career in careers}
    counts = Tally()

    for answers, chosen in choices:
        candidates = panel.candidate_ids(answers, careers)
        if candidates is None:
            continue  # q2 skipped -- the 16-way fallback, so no shortlist and no key
        counts.considered += 1
        counts.in_shortlist += chosen in candidates
        any_bonus, primary = key_targets(answers, [by_id[c] for c in candidates])
        if not any_bonus:
            continue  # every tie-breaker skipped: the key does not speak
        counts.key_speaks += 1
        counts.follows += chosen in any_bonus
        counts.follows_primary += chosen in primary

    return counts


def measure(votes: list[dict]) -> Measurement:
    """The readings, over the votes that produced the shipped silver labels."""
    labels = consensus_labels(votes)
    silver_votes = [vote for vote in votes if vote["profile_id"] in labels]

    #: one vote per profile carries that profile's answers; the label replaces `top1`
    answers_by_profile = {vote["profile_id"]: vote["answers"] for vote in silver_votes}

    return Measurement(
        prompt_version=panel.PROMPT_VERSION,
        votes=len(votes),
        profiles=len({vote["profile_id"] for vote in votes}),
        silver_profiles=len(labels),
        vote_level=tally((vote["answers"], vote["top1"]) for vote in silver_votes),
        label_level=tally(
            (answers, labels[profile_id])
            for profile_id, answers in answers_by_profile.items()
        ),
    )


def render(m: Measurement) -> str:
    votes, labels = m.vote_level, m.label_level
    return "\n".join([
        f"prompt version                        : {m.prompt_version}",
        f"error-free votes                      : {m.votes} over {m.profiles} profiles",
        f"high-consensus (silver) profiles      : {m.silver_profiles}",
        "",
        f"stage-2 votes on silver profiles      : {votes.considered}",
        f"  top-1 inside the stage-1 shortlist  : {votes.in_shortlist} = "
        f"{votes.shortlist_containment:.1%}  (structural -- the prompt allows nothing else)",
        f"  the key speaks (>=1 tie-breaker)    : {votes.key_speaks}",
        f"  top-1 follows the key, any bonus    : {votes.follows} = {votes.follow_rate:.1%}"
        "   <-- the quoted ~94%",
        f"  top-1 follows the key, +3 rules only: {votes.follows_primary} = "
        f"{votes.follow_rate_primary:.1%}",
        "",
        f"silver labels decided by stage 2      : {labels.considered} of {m.silver_profiles}",
        f"  the key speaks                      : {labels.key_speaks}",
        f"  the LABEL follows the key           : {labels.follows} = "
        f"{labels.follow_rate:.1%}",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--votes", type=Path, default=VOTE_LOG)
    parser.add_argument("--json", action="store_true", help="emit the raw counts")
    args = parser.parse_args()

    measurement = measure(load_votes(args.votes))
    print(json.dumps(asdict(measurement), indent=2) if args.json
          else render(measurement))


if __name__ == "__main__":
    main()
