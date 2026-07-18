"""Shared feature assembly for the learned matcher (matching rework Phase 1).

One place defines the feature vector; the offline training script
(data/scripts/build_training_set.py) and — once a model ships — the serving path
both import it, so train/serve feature drift is impossible by construction.

Layout (FEATURE_NAMES gives the exact order):

    q1..qN           raw ordinal answers 0-3 (0 when missing)          N dims
    q1_present..     1.0 if answered, 0.0 if skipped or branched away  N dims
    <career>_fit     questionnaire_fit per career, normalized to the
                     strongest-fitting career (mirrors matching_service) 16 dims
    <career>_sem     semantic similarity per career (ChromaDB, 0 when
                     the field returned no ads)                          16 dims
    <career>_skill   key-skill overlap per career against market skills  16 dims

Question order is the questions.json bank order and career order is the
careers.json catalog order — both stable because they are versioned with the code.
Bump FEATURE_VERSION on ANY change to this layout; a model artifact trained on one
version must never be fed vectors from another.
"""
from __future__ import annotations

from collections import Counter

from app.data import load_questions

# features-v4: question bank grew 13 -> 18 (q14-q17 career-family follow-ups gated
# on q2, q18 linear), so the raw-answer/presence blocks are wider. Older artifacts
# are refused on load; matching falls back to the formula until a model is
# retrained (pipeline: docs/matching-rework-plan.md).
FEATURE_VERSION = "features-v4"

QUESTION_IDS = [q["id"] for q in load_questions()]


def raw_fit(career: dict, answers: dict[str, int | None]) -> int:
    """Base+bonus questionnaire score for one career (same math as
    matching_service._raw_fit / data.js computeResults)."""
    score = 0
    for qid, weight in career["weights"].items():
        val = answers.get(qid)
        if val is not None:
            score += val * weight
    for rule in career.get("bonuses", []):
        if answers.get(rule["qId"]) == rule["answerValue"]:
            score += rule["bonus"] * 3
    return score


def questionnaire_fits(careers: list[dict], answers: dict[str, int | None]) -> dict[str, float]:
    """Per-career fit normalized to the strongest-fitting career (best ~ 1.0)."""
    raw = {c["id"]: raw_fit(c, answers) for c in careers}
    max_fit = max(raw.values()) or 1
    return {cid: score / max_fit for cid, score in raw.items()}


def skill_overlap(career: dict, market_skills: Counter) -> float:
    """Share of the career's curated key skills present in market demand."""
    key_skills = career["keySkills"]
    if not market_skills or not key_skills:
        return 0.0
    market_keys = set(market_skills)
    matched = sum(1 for s in key_skills if s.lower() in market_keys)
    return matched / len(key_skills)


def feature_names(careers: list[dict]) -> list[str]:
    names = list(QUESTION_IDS)
    names += [f"{qid}_present" for qid in QUESTION_IDS]
    names += [f"{c['id']}_fit" for c in careers]
    names += [f"{c['id']}_sem" for c in careers]
    names += [f"{c['id']}_skill" for c in careers]
    return names


def build_feature_vector(
    answers: dict[str, int | None],
    careers: list[dict],
    semantic: dict[str, float | None],
    market_skills: dict[str, Counter],
) -> list[float]:
    """Assemble the flat feature vector. `semantic` and `market_skills` are keyed by
    career id (what CareerRepository.get_candidates produces per candidate); missing
    entries degrade to 0.0 exactly like the current formula path."""
    vector: list[float] = []
    for qid in QUESTION_IDS:
        val = answers.get(qid)
        vector.append(float(val) if val is not None else 0.0)
    for qid in QUESTION_IDS:
        vector.append(1.0 if answers.get(qid) is not None else 0.0)

    fits = questionnaire_fits(careers, answers)
    for c in careers:
        vector.append(float(fits[c["id"]]))
    for c in careers:
        sim = semantic.get(c["id"])
        vector.append(float(sim) if sim is not None else 0.0)
    for c in careers:
        vector.append(skill_overlap(c, market_skills.get(c["id"]) or Counter()))
    return vector
