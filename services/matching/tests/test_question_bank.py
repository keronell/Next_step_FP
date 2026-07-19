"""DEV-29 definition-of-done: the question bank uniquely identifies every career.

- questions.json and every career's weights/bonuses in careers.json must agree.
- No two questions may carry the same matching signal (weight column + bonus rules
  across careers) — a duplicate signal means one question is redundant.
- For each career, a hand-authored archetype (a plausible full answer set from
  someone suited to that career, respecting the adaptive show_if branching) must
  rank that career strictly #1 on the raw questionnaire fit.
"""
from common.data import load_careers, load_questions
from app.services.feature_builder import raw_fit

CAREERS = load_careers()
QUESTIONS = load_questions()

# One archetype per career. Keys follow branching: q3 only when q2 in {1,2},
# q9 only when q2 in {0,1}, q14-q17 only on their q2 family branch (q14: q2=0,
# q15: q2=1, q16: q2=2, q17: q2=3), q18 always
# (enforced by test_archetypes_respect_branching).
ARCHETYPES = {
    "frontend": {"q1": 3, "q2": 0, "q4": 0, "q5": 1, "q6": 0, "q7": 1,
                 "q8": 1, "q9": 3, "q10": 0, "q11": 0, "q12": 2, "q13": 0,
                 "q14": 0, "q18": 2},
    "backend": {"q1": 3, "q2": 1, "q3": 2, "q4": 1, "q5": 1, "q6": 1, "q7": 1,
                "q8": 1, "q9": 0, "q10": 1, "q11": 1, "q12": 2, "q13": 1,
                "q15": 3, "q18": 3},
    "data-science": {"q1": 2, "q2": 2, "q3": 3, "q4": 1, "q5": 2, "q6": 1, "q7": 2,
                     "q8": 2, "q10": 2, "q11": 2, "q12": 3, "q13": 2,
                     "q16": 1, "q18": 0},
    "devops": {"q1": 2, "q2": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3,
               "q8": 3, "q10": 3, "q11": 3, "q12": 2, "q13": 3,
               "q17": 0, "q18": 0},
    # q16 is the data-family follow-up a PM-leaning q2=2 answerer still receives;
    # every option boosts a data career, so the plausible archetype answer is a skip.
    "product-manager": {"q1": 0, "q2": 2, "q3": 2, "q4": 2, "q5": 0, "q6": 0, "q7": 1,
                        "q8": 0, "q10": 2, "q11": 2, "q12": 0, "q13": 2,
                        "q16": None, "q18": 1},
    "ux-designer": {"q1": 0, "q2": 0, "q4": 0, "q5": 0, "q6": 0, "q7": 0,
                    "q8": 0, "q9": 3, "q10": 0, "q11": 0, "q12": 1, "q13": 0,
                    "q14": 3, "q18": 0},
    "fullstack": {"q1": 3, "q2": 1, "q3": 1, "q4": 0, "q5": 1, "q6": 2, "q7": 1,
                  "q8": 1, "q9": 1, "q10": 1, "q11": 1, "q12": 2, "q13": 1,
                  "q15": 0, "q18": 3},
    "mobile": {"q1": 3, "q2": 0, "q4": 0, "q5": 1, "q6": 1, "q7": 1,
               "q8": 1, "q9": 2, "q10": 0, "q11": 0, "q12": 2, "q13": 0,
               "q14": 1, "q18": 2},
    "data-analyst": {"q1": 1, "q2": 2, "q3": 3, "q4": 2, "q5": 2, "q6": 2, "q7": 2,
                     "q8": 2, "q10": 2, "q11": 2, "q12": 3, "q13": 2,
                     "q16": 0, "q18": 0},
    "machine-learning": {"q1": 3, "q2": 2, "q3": 3, "q4": 1, "q5": 1, "q6": 1, "q7": 2,
                         "q8": 2, "q10": 1, "q11": 2, "q12": 2, "q13": 1,
                         "q16": 2, "q18": 0},
    "ai-engineer": {"q1": 3, "q2": 2, "q3": 2, "q4": 0, "q5": 1, "q6": 1, "q7": 2,
                    "q8": 1, "q10": 0, "q11": 2, "q12": 2, "q13": 1,
                    "q16": 3, "q18": 0},
    "cyber-security": {"q1": 2, "q2": 3, "q4": 3, "q5": 3, "q6": 1, "q7": 2,
                       "q8": 3, "q10": 3, "q11": 3, "q12": 3, "q13": 3,
                       "q17": 1, "q18": 0},
    "qa-engineer": {"q1": 2, "q2": 1, "q3": 1, "q4": 3, "q5": 1, "q6": 1, "q7": 1,
                    "q8": 1, "q9": 1, "q10": 1, "q11": 1, "q12": 3, "q13": 3,
                    "q15": 2, "q18": 0},
    "game-dev": {"q1": 3, "q2": 0, "q4": 0, "q5": 1, "q6": 1, "q7": 1,
                 "q8": 1, "q9": 3, "q10": 0, "q11": 0, "q12": 2, "q13": 1,
                 "q14": 2, "q18": 2},
    # Same for the builder-family q15 under q2=1: no option fits a writer, so skip.
    "technical-writer": {"q1": 1, "q2": 1, "q3": 1, "q4": 2, "q5": 2, "q6": 2, "q7": 0,
                         "q8": 0, "q9": 2, "q10": 0, "q11": 0, "q12": 0, "q13": 0,
                         "q15": None, "q18": 0},
    "software-architect": {"q1": 3, "q2": 1, "q3": 2, "q4": 1, "q5": 3, "q6": 3, "q7": 1,
                           "q8": 1, "q9": 0, "q10": 1, "q11": 3, "q12": 0, "q13": 1,
                           "q15": 1, "q18": 0},
}


def _signal(qid: str) -> tuple:
    """A question's full matching signal: per career, its weight and bonus rules."""
    sig = []
    for c in CAREERS:
        rules = tuple(sorted(
            (r["answerValue"], r["bonus"]) for r in c.get("bonuses", []) if r["qId"] == qid
        ))
        sig.append((c["weights"].get(qid, 0), rules))
    return tuple(sig)


def _visible_ids(answers: dict) -> set[str]:
    return {
        q["id"] for q in QUESTIONS
        if "show_if" not in q or answers.get(q["show_if"]["q"]) in q["show_if"]["in"]
    }


def test_questions_and_career_weights_agree():
    qids = {q["id"] for q in QUESTIONS}
    for career in CAREERS:
        assert set(career["weights"]) == qids, career["id"]
        for rule in career.get("bonuses", []):
            assert rule["qId"] in qids, career["id"]
    for q in QUESTIONS:
        # QuestionnaireSubmission hardcodes the 0-3 answer range
        assert len(q["options"]) == 4, q["id"]


def test_no_two_questions_share_a_signal():
    signals = {}
    for q in QUESTIONS:
        sig = _signal(q["id"])
        assert any(w for w, _ in sig) or any(rules for _, rules in sig), \
            f"{q['id']} contributes nothing to matching"
        assert sig not in signals, f"{q['id']} duplicates {signals.get(sig)}'s signal"
        signals[sig] = q["id"]


def test_archetypes_respect_branching():
    assert set(ARCHETYPES) == {c["id"] for c in CAREERS}
    for cid, answers in ARCHETYPES.items():
        assert set(answers) == _visible_ids(answers), cid


def test_every_career_uniquely_identifiable():
    for cid, answers in ARCHETYPES.items():
        scores = {c["id"]: raw_fit(c, answers) for c in CAREERS}
        runner_up = max(v for k, v in scores.items() if k != cid)
        assert scores[cid] > runner_up, f"{cid} not ranked strictly first: {scores}"
