"""Explainable career matching: learned model when available, formula fallback.

When a Matcher artifact is loaded (MATCHER_MODEL_PATH set + valid), scoring is
its probability output over the catalog careers (trained on synthetic silver labels —
see docs/matching-rework-plan.md), with attribution-driven reasons. On ANY model
error — or when no model is configured (the default) — scoring falls back to the
original deterministic blend below, same defensive posture as the ChromaDB/Supabase
fallbacks:

    final = 0.40 * questionnaire_fit      # how the user's answers weight toward this career
          + 0.40 * semantic_similarity    # how close their profile is to real job ads (ChromaDB)
          + 0.20 * skill_overlap          # share of the career's key skills seen in market demand

When the user filled the DEV-60 self-input profile, PROFILE_WEIGHTS is used instead:
their own skills earn a 0.20 slice taken from the two MARKET-derived components
(semantic 0.40 -> 0.30, skill_overlap 0.20 -> 0.10). `questionnaire_fit` keeps its
weight — the quiz stays the primary signal, the profile refines it.

Either way the response dict shape is identical; `model_version` records which
scorer produced it.

Assumptions / notes:
- `questionnaire_fit` reuses the frontend's WEIGHTS+BONUSES logic (ported from
  data.js) and is normalized *relative to the strongest-fitting career*, so the best
  questionnaire match sits near 1.0. This mirrors the existing UX.
- `semantic_similarity` comes straight from ChromaDB (cosine -> 1-distance, already
  0..1). A career whose field has no job ads gets 0 here — missing data is never
  rewarded, it just can't earn the semantic component.
- `skill_overlap` compares the career's curated key skills against skills aggregated
  from the retrieved job ads. Empty market data -> 0. It is a property of the CAREER
  and the market, identical for every user.
- `user_skill_match` (profile only) is the first per-USER skill signal: the share of
  the career's key skills the user actually claims, credited also for the field's
  in-demand market skills they already hold.
- Ties broken by career id (ascending) for stable output.
"""
from __future__ import annotations

import math
import re

from common.logging import get_logger
from common.data import load_questions
from common.models.profile import UserProfile
from common.profile_text import canonical_skills
from app.repositories.career_repository import CareerCandidate
from app.services import feature_builder, reason_builder
from app.services.matcher import Matcher, displays_own_percentages

logger = get_logger(__name__)

# The one place the formula weights live. Both sets must sum to 1.0.
FORMULA_WEIGHTS = {
    "questionnaire_fit": 0.40,
    "semantic_similarity": 0.40,
    "skill_overlap": 0.20,
}
# DEV-60: used only when a non-empty self-input profile came with the request, so a
# skipped profile scores byte-identically to the pre-DEV-60 formula.
PROFILE_WEIGHTS = {
    "questionnaire_fit": 0.40,
    "semantic_similarity": 0.30,
    "skill_overlap": 0.10,
    "user_skill_match": 0.20,
}
for _weights in (FORMULA_WEIGHTS, PROFILE_WEIGHTS):
    assert abs(sum(_weights.values()) - 1.0) < 1e-9, "matching weights must sum to 1"

FORMULA_VERSION = "formula-v1"
PROFILE_FORMULA_VERSION = "formula-v1+profile"

TOP_N = 3
MAX_MISSING_SKILLS = 5
# A market skill only counts toward user_skill_match if employers ask for it often
# enough to be a real credential — one stray ad shouldn't earn profile credit.
MIN_MARKET_MENTIONS = 2


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
    """Returns (skill_overlap, matched_skills, missing_skills).

    MARKET view (no self-input profile): what this career's key skills look like
    against employer demand. Identical for every user.
    """
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


def _strong_market_skills(candidate: CareerCandidate) -> set[str]:
    """Field skills asked for by at least MIN_MARKET_MENTIONS ads."""
    return {s for s, n in candidate.market_skills.items() if n >= MIN_MARKET_MENTIONS}


def _squash(skill: str) -> str:
    """Compare skills ignoring spacing and punctuation: "Power BI", "power bi" and
    "powerbi" are one skill.

    The scraped corpus and the curated keySkills disagree on spacing constantly, and
    the alias map covers spellings ("reactjs") rather than spacing. Without this a
    user who types "PowerBI" earns no credit for the "Power BI" key skill, and the
    gap list shows the same skill twice in two spellings. `+` and `#` survive so C++
    and C# stay distinct (same reasoning as roadmap_service._SLUG_SYMBOLS).
    """
    return re.sub(r"[^a-z0-9+#]", "", skill.lower())


def _user_skill_signals(
    career: dict, candidate: CareerCandidate, user_skills: set[str]
) -> tuple[list[str], list[str]]:
    """USER view (self-input profile present): what THEY have and lack for this career.

    This is the semantics Roadmap.jsx has always claimed — `matched_skills` renders as
    "you may already have this skill" and `missing_skills` colors gap nodes orange.
    Before DEV-60 both were market-derived, so those labels were untrue.
    """
    key_skills = career["keySkills"]
    held = {_squash(s) for s in user_skills}
    matched = [s for s in key_skills if _squash(s) in held]
    missing = [s for s in key_skills if _squash(s) not in held]

    # Top up the gaps with in-demand field skills they don't have yet. `seen` spans
    # key skills, user skills AND everything already added, so the market's spelling
    # of a skill can never appear beside the curated one.
    seen = held | {_squash(s) for s in key_skills}
    for skill, count in candidate.market_skills.most_common():
        if len(missing) >= MAX_MISSING_SKILLS:
            break
        key = _squash(skill)
        if key in seen or count < MIN_MARKET_MENTIONS:
            continue
        seen.add(key)
        missing.append(skill.title())

    return matched, missing[:MAX_MISSING_SKILLS]


# Curated key skills discriminate between careers; market skills corroborate the
# field. Weighting them apart stops a user with generic skills (git, linux, sql)
# from scoring ~1.0 on every career at once.
_KEY_SKILL_SHARE = 0.7
_MARKET_SKILL_SHARE = 0.3


def _user_skill_match(career: dict, candidate: CareerCandidate, user_skills: set[str]) -> float:
    """How well the user's own skills fit this career, 0..1.

    Two normalizations on purpose:
      key_hits    = share of the CAREER's key skills the user holds
      market_hits = share of the USER's skills this field actually asks for
    The second denominator is what makes it discriminating — a data analyst's skill
    set is wanted far more by Data Analysis than by Game Development.
    """
    held = {_squash(s) for s in user_skills}
    if not held:
        return 0.0
    key_skills = career["keySkills"]
    key_hits = (
        sum(1 for s in key_skills if _squash(s) in held) / len(key_skills)
        if key_skills
        else 0.0
    )
    market = {_squash(s) for s in _strong_market_skills(candidate)}
    market_hits = len(held & market) / len(held) if market else 0.0
    return _KEY_SKILL_SHARE * key_hits + _MARKET_SKILL_SHARE * market_hits


def _reasons(
    fit: float,
    semantic: float,
    matched: list[str],
    career: dict,
    user_skills: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if fit >= 0.85:
        reasons.append("Strong alignment with your interests and work style")
    elif fit >= 0.5:
        reasons.append("Good fit with how you answered the questionnaire")
    if semantic >= 0.4:
        reasons.append(f"Closely matches real {career['field']} job postings")
    if matched:
        # With a profile, `matched` is what the USER has — say so; otherwise it is
        # the career's key skills seen in employer demand.
        reasons.append(
            reason_builder.user_skill_reason(career, matched)
            if user_skills
            else "Builds on in-demand skills like " + ", ".join(matched[:3])
        )
    if len(reasons) < 2:
        reasons.append("A direction worth exploring based on your responses")
    return reasons[:4]


def match(
    answers: dict[str, int | None],
    candidates: list[CareerCandidate],
    model: Matcher | None = None,
    profile: UserProfile | None = None,
) -> list[dict]:
    """Score candidates and return the top N as plain dicts (sorted, deduped).

    Uses the learned model when one is supplied, falling back to the formula on
    any model failure; without a model this is exactly the original formula path.

    `profile` (DEV-60) already shaped the embedding upstream, so the model path
    picks it up through its `<career>_sem` features; the formula path additionally
    scores the user's own skills (see PROFILE_WEIGHTS).
    """
    if not candidates:
        return []
    if model is not None:
        try:
            return _match_model(answers, candidates, model, profile)
        except Exception:
            logger.exception("Learned matcher failed; falling back to formula")
    return _match_formula(answers, candidates, profile)


def _profile_context(profile: UserProfile | None) -> tuple[bool, set[str]]:
    """(has_profile, user_skills) — two INDEPENDENT questions, deliberately.

    A user who filled only Experience and Projects has a real profile but no skill
    tags. That must not fall back to the legacy path: the market-derived
    matched_skills would be presented to them as "skills you already have" (see
    Roadmap.jsx), which is exactly the untruth DEV-60 exists to remove. So labeling
    keys off has_profile, while the user_skill_match COMPONENT keys off user_skills
    — scoring it with an empty skill set would just subtract 0.20 from every career
    equally, changing no ranking and deflating every percentage.

    # ponytail: prose is not mined for skills. If experience-only profiles turn out
    # to be common, run the description through data/scripts/extract_skills.py's
    # SKILL_PATTERNS instead of adding a second heuristic here.
    """
    if profile is None or profile.is_empty:
        return False, set()
    return True, canonical_skills(profile)


def _match_model(
    answers: dict[str, int | None],
    candidates: list[CareerCandidate],
    model: Matcher,
    profile: UserProfile | None = None,
) -> list[dict]:
    """Score with the learned artifact; response shape identical to the formula path.

    The profile does NOT re-weight the score here — that is PROFILE_WEIGHTS, a
    formula concept. The model already sees the profile through its `<career>_sem`
    features (build_profile shaped the embedding upstream). But matched/missing
    skills must still be user-derived: Roadmap.jsx colors gap nodes from them, so
    leaving them market-derived would tell a profile user they lack skills they
    just entered — and mark ones they never claimed as already held.
    """
    seen: set[str] = set()
    unique = []
    for cand in candidates:
        if cand.career["id"] in seen:
            continue
        seen.add(cand.career["id"])
        unique.append(cand)

    careers = [c.career for c in unique]
    names = feature_builder.feature_names(careers)
    if names != model.feature_names:
        raise ValueError("candidate careers do not match the model's feature layout")

    semantic = {c.career["id"]: c.semantic_similarity for c in unique}
    market = {c.career["id"]: c.market_skills for c in unique}
    vector = feature_builder.build_feature_vector(answers, careers, semantic, market)
    probs = model.predict_proba(vector)
    # Load-time validation rejects non-finite artifact weights, but finite weights
    # can still overflow to inf/NaN during inference. Raising here reaches `match()`,
    # which falls back to the formula; letting it through would put NaN in
    # `score_breakdown.model_probability` on the ranking_only path -- where nothing
    # else raises, because the formula supplies every displayed field -- and fail at
    # response serialization instead, outside the fallback.
    if any(not math.isfinite(p) for p in probs.values()):
        raise ValueError(
            f"{model.version} produced non-finite probabilities; falling back"
        )

    fits = feature_builder.questionnaire_fits(careers, answers)
    questions_by_id = {q["id"]: q for q in load_questions()}
    by_id = {c.career["id"]: c for c in unique}

    has_profile, user_skills = _profile_context(profile)
    top = sorted(probs, key=lambda cid: (-probs[cid], cid))[:TOP_N]

    # ADR 0005's mitigable-ECE branch. A `ranking_only` artifact selects the careers
    # but does not put a number beside them: every figure the user sees -- the
    # percentage, the score and the breakdown that explains it -- is the formula's,
    # and the list is ORDERED by that percentage so the top row always carries the
    # highest one. That ordering is an amendment to the ADR as originally written
    # ("ships as the ranking source"): within the selected set the order is the
    # formula's, so the model contributes the SELECTION, not the ranking. Recorded in
    # docs/adr/0005-gate-1-is-a-ship-floor.md.
    #
    # `reasons` stay model-derived on purpose: they explain why this career was
    # selected, which is the one judgement the model is still trusted to make.
    formula_by_id: dict[str, dict] = {}
    if not displays_own_percentages(model):
        formula_by_id = {r["id"]: r for r in _formula_scored(answers, unique, profile)}
        top.sort(key=_display_order(formula_by_id.get))

    results: list[dict] = []
    for cid in top:
        cand = by_id[cid]
        career = cand.career
        overlap, matched, missing = _skill_signals(career, cand)
        if has_profile:
            matched, missing = _user_skill_signals(career, cand, user_skills)
        contributions = model.contributions(vector, cid)
        displayed = formula_by_id.get(cid)
        if displayed is None:
            breakdown = {
                "semantic_similarity": round(cand.semantic_similarity or 0.0, 3),
                "questionnaire_fit": round(fits[cid], 3),
                "skill_overlap": round(overlap, 3),
            }
        else:
            # The breakdown has to explain the number actually on screen, so it comes
            # from the same scorer -- including its user_skill_match component when
            # the profile selected PROFILE_WEIGHTS. Copied rather than aliased: the
            # source dict is still owned by `formula_by_id`.
            breakdown = dict(displayed["score_breakdown"])
            # What the model produced, kept because it is no longer displayed
            # anywhere: without it the selection behind this list is unauditable
            # from the response or the persisted history.
            breakdown["model_probability"] = round(probs[cid], 3)
        results.append(
            {
                "id": cid,
                "title": career["title"],
                "description": career["description"],
                "keySkills": career["keySkills"],
                "icon": career["icon"],
                "roadmapKey": career["roadmapKey"],
                "matchPercent": (
                    displayed["matchPercent"] if displayed else round(probs[cid] * 100)
                ),
                "score": displayed["score"] if displayed else round(probs[cid], 3),
                "score_breakdown": breakdown,
                "reasons": reason_builder.build_reasons(
                    career, answers, contributions, matched, questions_by_id, bool(user_skills)
                ),
                "matched_skills": matched,
                "missing_skills": missing,
                "model_version": model.version,
                # Embedded per-recommendation (not only response-level) so the
                # persisted jsonb and the history restore path carry the artifact's
                # training-data warnings wherever these recs travel.
                "model_caveats": model.caveats,
            }
        )
    return results


def _display_order(lookup):
    """Sort key putting the highest DISPLAYED percentage first.

    Ordering on `score` alone is not enough, and the difference is not theoretical:
    `score` is `round(final, 3)` while `matchPercent` is `round(final * 100)`, so two
    careers can tie at three decimals and still straddle a half-percent boundary --
    0.49520 and 0.49468 are both `score` 0.495 but display 50 and 49. Under a
    score-then-id key the 49 can print above the 50, which is precisely the
    non-monotonic display ADR 0005's amendment exists to prevent.

    Keying on the displayed integer first makes the invariant true by construction.
    `score` then breaks ties within a shared percentage, and the id last keeps the
    order deterministic.
    """
    def key(cid_or_rec):
        rec = lookup(cid_or_rec)
        return (-rec["matchPercent"], -rec["score"], rec["id"])

    return key


def _formula_scored(
    answers: dict[str, int | None],
    candidates: list[CareerCandidate],
    profile: UserProfile | None = None,
) -> list[dict]:
    """Every candidate scored and shaped by the formula — unsorted, untruncated.

    Split out of `_match_formula` for ADR 0005's mitigation: a `ranking_only` model
    displays the formula's percentages, and the careers it ranks need not be the ones
    the formula would have returned. Truncating to TOP_N before that lookup would
    leave a model-selected career with no percentage computed anywhere, which is why
    the sort and the slice live in the caller rather than here.

    Note `fit` is normalized against the strongest fit among `candidates`, so this is
    only meaningful over the full candidate set — pass every candidate, not a subset.
    """
    raw_fits = {c.career["id"]: _raw_fit(c.career, answers) for c in candidates}
    max_fit = max(raw_fits.values()) or 1  # avoid divide-by-zero

    # A skipped or emptied profile takes the original path unchanged.
    has_profile, user_skills = _profile_context(profile)
    weights = PROFILE_WEIGHTS if user_skills else FORMULA_WEIGHTS

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
            weights["questionnaire_fit"] * fit
            + weights["semantic_similarity"] * semantic
            + weights["skill_overlap"] * overlap
        )
        breakdown = {
            "semantic_similarity": round(semantic, 3),
            "questionnaire_fit": round(fit, 3),
            "skill_overlap": round(overlap, 3),
        }

        if user_skills:
            user_match = _user_skill_match(career, cand, user_skills)
            final += weights["user_skill_match"] * user_match
            breakdown["user_skill_match"] = round(user_match, 3)
        if has_profile:
            # Empty user_skills -> matched=[], missing=the career's key skills. "We
            # don't know what you know" is the honest answer; claiming market skills
            # as theirs is not.
            matched, missing = _user_skill_signals(career, cand, user_skills)

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
                "score_breakdown": breakdown,
                "reasons": _reasons(fit, semantic, matched, career, bool(user_skills)),
                "matched_skills": matched,
                "missing_skills": missing,
                # Stamped from has_profile, not user_skills: an experience-only
                # profile still reshaped the embedding, so "formula-v1" would
                # misreport how this score was produced.
                "model_version": PROFILE_FORMULA_VERSION if has_profile else FORMULA_VERSION,
                "model_caveats": [],  # formula path: no learned-model warnings
            }
        )

    return scored


def _match_formula(
    answers: dict[str, int | None],
    candidates: list[CareerCandidate],
    profile: UserProfile | None = None,
) -> list[dict]:
    scored = _formula_scored(answers, candidates, profile)
    # Same key as the ranking-only path: the displayed percentage leads, so the top
    # row always carries the highest number here too. Measured at 0 of 4000 draws on
    # this path (1 of 4000 on the ranking-only path), so this is a latent tie being
    # closed rather than a live defect -- but the invariant should not depend on how
    # often the tie happens to come up.
    scored.sort(key=_display_order(lambda r: r))
    return scored[:TOP_N]
