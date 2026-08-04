"""DEV-89: every question in the bank reaches the reason builder.

`QUESTION_PHRASES` is both the phrase mapping and the iteration set, so a question
absent from it has its attribution computed by the matcher and then discarded. The
bank grew to 18 while the mapping stopped at q10, dropping 44% of the
question-feature surface -- and the dropped half is q11-q18, the pure
discriminators a learned model leans on hardest.

A coverage assertion alone is too weak: it catches a missing q19 but not a phrase
that exists and is wrong, nor a question block that stops being reachable for some
other reason. So the plan asks for three tests, and they are three different
questions:

  coverage        -- is every id phrased?
  attribution mass-- is the phrased set actually where the model's explainable
                     mass lives, measured against the explainable universe?
  wording drift   -- does the phrase still describe the question a human wrote?

The mass metric's denominator, and the three judgement calls inside it, are
documented once in `reason_diagnostics.py`; this module imports that computation
rather than reimplementing it, so the asserted number and the number in the
DEV-89 reproduction record cannot drift apart.
"""
import json
from pathlib import Path

import pytest

from app.services.matcher_model import MatcherModel
from app.services.reason_builder import QUESTION_PHRASES, build_reasons
from common.data import load_careers, load_questions
from tests.reason_diagnostics import (
    ANSWER_SETS,
    DEFAULT_ARTIFACT,
    MASS_BAR,
    PRE_DEV89_PHRASED,
    SNAPSHOT,
    answer_sets,
    candidates,
    measure,
)

QUESTIONS = load_questions()
QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}
CAREERS = load_careers()
FRONTEND = next(c for c in CAREERS if c["id"] == "frontend")


# ------------------------------------------------------------------- coverage
def test_every_question_in_the_bank_has_a_phrase():
    """The mapping is the iteration set, so a gap here silently drops attribution.

    Asserted in both directions: a missing id is the DEV-89 defect, and a stale id
    means a question was removed from the bank while its phrase lingered, which
    would leave dead wording for a human to trip over during the drift review.
    """
    bank = {q["id"] for q in QUESTIONS}
    phrased = set(QUESTION_PHRASES)
    assert bank - phrased == set(), f"questions with no phrase: {sorted(bank - phrased)}"
    assert phrased - bank == set(), f"phrases for absent questions: {sorted(phrased - bank)}"


@pytest.mark.parametrize("qid", [q["id"] for q in QUESTIONS])
def test_every_question_can_render_a_reason(qid):
    """End-to-end: attribution on any single question becomes a sentence.

    Coverage of the dict is necessary but not sufficient -- this drives the real
    `build_reasons`, so it also fails if the iteration or lookup path stops
    reaching a question for a reason other than a missing key. The gated questions
    (q14-q17) are answered directly here: `build_reasons` gates on the answer being
    present, not on `show_if`, and one of the four is always present in serving.
    """
    answer = 1
    reasons = build_reasons(
        FRONTEND, {qid: answer}, {qid: 0.9}, [], QUESTIONS_BY_ID,
    )
    quoted = QUESTIONS_BY_ID[qid]["options"][answer]
    assert any(quoted in r and QUESTION_PHRASES[qid] in r for r in reasons), (
        f"{qid} produced no sentence quoting its answer: {reasons}"
    )


# ----------------------------------------------------------- attribution mass
@pytest.fixture(scope="module")
def shipped_model() -> MatcherModel:
    """The artifact actually checked in, not a fixture with invented coefficients.

    Deliberately not skipped when absent: the whole criterion is about where a real
    model's mass lands, so a silent skip would retire the acceptance test.
    """
    assert DEFAULT_ARTIFACT.exists(), f"shipped artifact missing: {DEFAULT_ARTIFACT}"
    return MatcherModel.load(DEFAULT_ARTIFACT)


def test_renderable_attribution_mass_clears_the_bar(shipped_model):
    """>= 0.99 of explainable mass has a rendering path, per DEV-89's criterion.

    The explainable universe is own-career fit/sem/skill plus all question
    features; cross-career coefficients are excluded because they are withheld from
    users on purpose. This is a WIDER denominator than the question-only reading
    reported alongside DEV-99, so the two numbers differ by design and neither
    should be quoted for the other.

    Renderability is probed from `build_reasons` rather than read off
    `QUESTION_PHRASES` -- see choice 2 in `reason_diagnostics`. That is what stops
    this from being a restatement of the coverage test above: it also fails if a
    question is phrased but the function still cannot render it.
    """
    stats = measure(shipped_model, candidates(), answer_sets(ANSWER_SETS))
    assert stats["explanations"] > 0
    assert stats["mean"] >= MASS_BAR, f"mean renderable share {stats['mean']:.3f}"
    assert stats["min"] >= MASS_BAR, (
        f"{stats['below_bar']} of {stats['explanations']} explanations fell below "
        f"the bar (worst {stats['min']:.3f})"
    )


def test_the_mass_metric_would_have_caught_the_defect(shipped_model):
    """The bar is not vacuous: the pre-DEV-89 mapping fails it, and badly.

    Without this, a metric that reads 1.000 proves nothing -- it could be measuring
    a denominator that can never contain an unrenderable feature. Restricting the
    phrased set to q1-q10 reconstructs exactly the state this ticket replaced and
    shows the same computation rejecting it, so the passing number above is
    evidence about the fix rather than about the metric.
    """
    intact = dict(QUESTION_PHRASES)
    stats = measure(
        shipped_model, candidates(), answer_sets(ANSWER_SETS), phrased=PRE_DEV89_PHRASED
    )
    assert stats["mean"] < MASS_BAR
    assert stats["below_bar"] > stats["explanations"] // 2, (
        "the pre-DEV-89 mapping should fail the bar on most explanations, but only "
        f"{stats['below_bar']} of {stats['explanations']} fell below it"
    )
    # The counterfactual reconstructs the old state by mutating the live mapping,
    # since that dict is also the iteration set. A leak would silently un-fix the
    # defect for every test that runs after this one, so it is checked, not trusted.
    assert QUESTION_PHRASES == intact, "phrase mapping not restored after measure()"


# ------------------------------------------------------------- wording drift
def test_question_wording_matches_the_phrase_snapshot():
    """Force a human re-read when question wording changes.

    Automation cannot check that "the role you gravitate to in a team" describes q5
    -- only a person can. What it can do is refuse to let the question change
    silently underneath the phrase, which is a demonstrated failure mode here:
    DEV-73 reworded q7 after these phrases were authored, and nothing complained.

    Options are snapshotted alongside the question text because the rendered
    sentence quotes the chosen OPTION and appends the phrase, so an option rewrite
    can strand a phrase just as easily as a text rewrite.

    On failure, re-read the phrase against the new wording, then regenerate the
    snapshot deliberately -- never as a reflex to make the suite green:

        python tests/reason_diagnostics.py --write-snapshot
    """
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current = [
        {
            "id": q["id"],
            "phrase": QUESTION_PHRASES.get(q["id"]),
            "text": q["text"],
            "options": q["options"],
        }
        for q in QUESTIONS
    ]
    # Report ids only: the bank uses characters a cp1252 console cannot print, and
    # the ids are what a reader needs to find the entries in the snapshot anyway.
    drifted = sorted(
        {e["id"] for e in expected} ^ {c["id"] for c in current}
        | {c["id"] for c, e in zip(current, expected) if c != e}
    )
    assert not drifted, (
        f"question wording or phrasing changed for {drifted}. Re-read each phrase "
        f"against the new wording, then regenerate {SNAPSHOT.name}."
    )
