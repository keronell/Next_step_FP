"""Attribution-driven `reasons` for the learned matcher (rework Phase 4).

Turns MatcherModel.contributions() into the same shape the frontend already
renders: a list of up to 4 short human sentences. Only human-explainable features
become reasons:

    qN / qN_present      -> the user's actual answer text, via a per-question phrase
    <career>_fit         -> questionnaire-alignment sentence (same career only)
    <career>_sem         -> job-posting similarity sentence (same career only)
    <career>_skill       -> in-demand-skills sentence, with matched skill names

Cross-career coefficients (e.g. devops_fit pushing *against* frontend) are real
model behavior but read as nonsense to users, so they never surface here.
"""
from __future__ import annotations

# Human descriptor per question, phrased to follow "your ...".
QUESTION_PHRASES = {
    "q1": "comfort with writing code",
    "q2": "what excites you most",
    "q3": "curiosity about data",
    "q4": "the kind of work output you value",
    "q5": "the role you gravitate to in a team",
    "q6": "preferred way of working",
    "q7": "the tools that appeal to you",
    "q8": "how you respond when a project goes sideways",
    "q9": "your draw to visual design",
    "q10": "what success means to you",
}

MAX_REASONS = 4
MAX_QUESTION_REASONS = 2
MIN_CONTRIBUTION = 0.05  # ignore noise-level attributions


def user_skill_reason(career: dict, matched_skills: list[str]) -> str:
    """The one place the 'skills you already have' sentence is worded — both the
    formula and the model path say it identically (DEV-60)."""
    return (
        f"You already have {len(matched_skills)} of the {len(career['keySkills'])} "
        "key skills: " + ", ".join(matched_skills[:3])
    )


def build_reasons(
    career: dict,
    answers: dict[str, int | None],
    contributions: dict[str, float],
    matched_skills: list[str],
    questions_by_id: dict[str, dict],
    user_skills: bool = False,
) -> list[str]:
    cid = career["id"]
    reasons: list[str] = []

    # Signal-level sentences, gated by their attribution for THIS career.
    if contributions.get(f"{cid}_fit", 0.0) > MIN_CONTRIBUTION:
        reasons.append("Strong alignment with how you answered the questionnaire")
    if contributions.get(f"{cid}_sem", 0.0) > MIN_CONTRIBUTION:
        reasons.append(f"Your profile reads like real {career['field']} job postings")
    if matched_skills and user_skills:
        # Not gated on the `_skill` attribution: that feature is the MARKET overlap,
        # which says nothing about what the user themselves entered.
        reasons.append(user_skill_reason(career, matched_skills))
    elif contributions.get(f"{cid}_skill", 0.0) > MIN_CONTRIBUTION and matched_skills:
        reasons.append("Builds on in-demand skills like " + ", ".join(matched_skills[:3]))

    # Question-level sentences: top answered questions by attribution (ordinal +
    # presence mask combined), quoting the user's own answer.
    q_scores: dict[str, float] = {}
    for qid in QUESTION_PHRASES:
        total = contributions.get(qid, 0.0) + contributions.get(f"{qid}_present", 0.0)
        if answers.get(qid) is not None and total > MIN_CONTRIBUTION:
            q_scores[qid] = total
    for qid in sorted(q_scores, key=q_scores.get, reverse=True)[:MAX_QUESTION_REASONS]:
        q = questions_by_id.get(qid)
        val = answers[qid]
        if not q or not (0 <= val < len(q["options"])):
            continue
        reasons.append(f"You chose “{q['options'][val]}” - {QUESTION_PHRASES[qid]}")

    if not reasons:
        reasons.append("A direction worth exploring based on your responses")
    return reasons[:MAX_REASONS]
