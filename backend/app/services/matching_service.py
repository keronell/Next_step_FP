"""Deterministic, explainable career matching. No ML model.

Each career gets a final score in [0,1] blended from three signals:

    final = 0.40 * questionnaire_fit      # how the user's answers weight toward this career
          + 0.40 * semantic_similarity    # how close their profile is to real job ads (ChromaDB)
          + 0.20 * skill_overlap          # share of the career's key skills seen in market demand

Assumptions / notes:
- `questionnaire_fit` reuses the frontend's WEIGHTS+BONUSES logic (ported from
  data.js) and is normalized *relative to the strongest-fitting career*, so the best
  questionnaire match sits near 1.0. This mirrors the existing UX.
- `semantic_similarity` comes straight from ChromaDB (cosine -> 1-distance, already
  0..1). A career whose field has no job ads gets 0 here — missing data is never
  rewarded, it just can't earn the semantic component.
- `skill_overlap` compares the career's curated key skills against skills aggregated
  from the retrieved job ads. Empty market data -> 0.
- Ties broken by career id (ascending) for stable output.
"""
from __future__ import annotations

from app.repositories.career_repository import CareerCandidate

# The one place the formula weights live. Must sum to 1.0.
FORMULA_WEIGHTS = {
    "questionnaire_fit": 0.40,
    "semantic_similarity": 0.40,
    "skill_overlap": 0.20,
}
assert abs(sum(FORMULA_WEIGHTS.values()) - 1.0) < 1e-9, "matching weights must sum to 1"

TOP_N = 3
MAX_MISSING_SKILLS = 5


def _raw_fit(career: dict, answers: dict[str, int | None]) -> int:
    """Port of data.js computeResults base+bonus scoring for one career."""
    weights = career["weights"]
    score = 0
    for qid, weight in weights.items():
        val = answers.get(qid)
        if val is not None:
            score += val * weight
    for rule in career.get("bonuses", []):
        if answers.get(rule["qId"]) == rule["answerValue"]:
            score += rule["bonus"] * 3
    return score


def _skill_signals(career: dict, candidate: CareerCandidate) -> tuple[float, list[str], list[str]]:
    """Returns (skill_overlap, matched_skills, missing_skills)."""
    key_skills = career["keySkills"]
    market = candidate.market_skills  # Counter of lowercased skill tokens
    if not market:
        return 0.0, [], []

    market_keys = set(market)
    matched = [s for s in key_skills if s.lower() in market_keys]
    overlap = len(matched) / len(key_skills) if key_skills else 0.0

    key_lower = {s.lower() for s in key_skills}
    # Additional in-demand skills for this field the career card doesn't already list.
    missing = [
        skill.title()
        for skill, _ in market.most_common()
        if skill not in key_lower
    ][:MAX_MISSING_SKILLS]

    return overlap, matched, missing


def _reasons(fit: float, semantic: float, matched: list[str], field: str) -> list[str]:
    reasons: list[str] = []
    if fit >= 0.85:
        reasons.append("Strong alignment with your interests and work style")
    elif fit >= 0.5:
        reasons.append("Good fit with how you answered the questionnaire")
    if semantic >= 0.4:
        reasons.append(f"Closely matches real {field} job postings")
    if matched:
        reasons.append("Builds on in-demand skills like " + ", ".join(matched[:3]))
    if len(reasons) < 2:
        reasons.append("A direction worth exploring based on your responses")
    return reasons[:4]


def match(answers: dict[str, int | None], candidates: list[CareerCandidate]) -> list[dict]:
    """Score candidates and return the top N as plain dicts (sorted, deduped)."""
    if not candidates:
        return []

    raw_fits = {c.career["id"]: _raw_fit(c.career, answers) for c in candidates}
    max_fit = max(raw_fits.values()) or 1  # avoid divide-by-zero

    scored: list[dict] = []
    seen: set[str] = set()
    for cand in candidates:
        career = cand.career
        cid = career["id"]
        if cid in seen:  # dedupe defensively
            continue
        seen.add(cid)

        fit = raw_fits[cid] / max_fit
        semantic = cand.semantic_similarity or 0.0
        overlap, matched, missing = _skill_signals(career, cand)

        final = (
            FORMULA_WEIGHTS["questionnaire_fit"] * fit
            + FORMULA_WEIGHTS["semantic_similarity"] * semantic
            + FORMULA_WEIGHTS["skill_overlap"] * overlap
        )

        scored.append(
            {
                "id": cid,
                "title": career["title"],
                "description": career["description"],
                "keySkills": career["keySkills"],
                "icon": career["icon"],
                "roadmapKey": career["roadmapKey"],
                "matchPercent": round(final * 100),
                "score": round(final, 3),
                "score_breakdown": {
                    "semantic_similarity": round(semantic, 3),
                    "questionnaire_fit": round(fit, 3),
                    "skill_overlap": round(overlap, 3),
                },
                "reasons": _reasons(fit, semantic, matched, career["field"]),
                "matched_skills": matched,
                "missing_skills": missing,
            }
        )

    scored.sort(key=lambda r: (-r["score"], r["id"]))  # deterministic tie-break
    return scored[:TOP_N]
