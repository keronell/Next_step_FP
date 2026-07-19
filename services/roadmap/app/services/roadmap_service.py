"""Roadmap lookup + generation.

`get_roadmap(career_id, profile, missing_skills)` is the single seam the API calls.
When OpenAI is configured AND personalization context is supplied, it asks the LLM
to generate a roadmap tailored to the user's profile and missing skills; otherwise
(or on ANY failure) it returns the curated static roadmap from data/roadmaps.json.

The generated roadmap uses the SAME schema as the static one so the existing
frontend view (Roadmap.jsx: sections -> nodes) consumes it unchanged:
  { "sections": [ { "id","label","nodes":[
      {"id","label","level","type","description","resources":[{"title","url"}]} ] } ] }
"""
import json
import re

from common.config import get_settings
from common.logging import get_logger
from common.data import load_careers, load_roadmaps

logger = get_logger(__name__)

_LEVELS = {"beginner", "intermediate", "advanced"}
_TYPES = {"required", "good-to-know", "optional"}

_SYSTEM = (
    "You are a career mentor that designs learning roadmaps. "
    "You output ONLY a JSON object, no prose. The object has one key, \"sections\", "
    "an ordered list (earliest learning phase first) of "
    '{"id","label","nodes"} where each node is '
    '{"id","label","level","type","description","resources"}. '
    f'"level" is one of {sorted(_LEVELS)}; "type" is one of {sorted(_TYPES)}; '
    '"resources" is a list of {"title","url"} pointing to real, well-known learning '
    "resources. Keep ids short kebab-case. 3-4 sections, 2-4 nodes each."
)


def _career_title(career_id: str) -> str:
    for c in load_careers():
        if c["id"] == career_id:
            return c["title"]
    return career_id


def _build_prompt(
    career_id: str,
    profile: str | None,
    missing_skills: list[str],
    market_required: list[str] | None = None,
) -> str:
    parts = [f"Build a learning roadmap for becoming a {_career_title(career_id)}."]
    if profile:
        parts.append(f"The learner describes themselves: {profile}")
    if missing_skills:
        parts.append(
            "Prioritize and weave in these skills they are currently missing: "
            + ", ".join(missing_skills)
            + "."
        )
    if market_required:
        parts.append(
            "These skills are required across current job ads — make sure the roadmap "
            "covers them: " + ", ".join(market_required) + "."
        )
    parts.append("Order sections from foundational to advanced so it reads like a timeline.")
    return " ".join(parts)


def _validate(data: dict) -> dict:
    """Coerce the LLM output into the frontend schema; raise if unusable."""
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("LLM roadmap missing non-empty 'sections'")
    for s in sections:
        nodes = s.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("LLM roadmap section missing 'nodes'")
        for n in nodes:
            if n.get("level") not in _LEVELS:
                n["level"] = "intermediate"
            if n.get("type") not in _TYPES:
                n["type"] = "required"
            n.setdefault("description", "")
            res = n.get("resources")
            n["resources"] = res if isinstance(res, list) else []
    return {"sections": sections}


def _generate(
    career_id: str,
    profile: str | None,
    missing_skills: list[str],
    settings,
    market_required: list[str] | None = None,
) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _build_prompt(career_id, profile, missing_skills, market_required)},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    return _validate(json.loads(resp.choices[0].message.content))


def get_roadmap(
    career_id: str,
    profile: str | None = None,
    missing_skills: list[str] | None = None,
    market_required: list[str] | None = None,
) -> dict | None:
    """Personalized LLM roadmap when possible; static data/roadmaps.json otherwise.

    Falls back to static on: no OpenAI key, no personalization context, or any LLM
    error — so the endpoint always returns something the frontend can render.
    `market_required` (in-demand skills from job ads) is only fed to the LLM prompt;
    the deterministic In-Demand section is added separately by inject_requirements().
    """
    static = load_roadmaps().get(career_id)
    settings = get_settings()
    if settings.openai_api_key and (profile or missing_skills):
        try:
            generated = _generate(career_id, profile, missing_skills or [], settings, market_required)
            logger.info("Generated LLM roadmap for %s", career_id)
            return generated
        except Exception:  # noqa: BLE001 - never fail the request over LLM problems
            logger.warning("LLM roadmap generation failed for %s; using static", career_id, exc_info=True)
    return static


# Symbols that distinguish otherwise-identical skill names must survive slugging:
# stripping them made "C#" and "C++" both collapse to "c" (duplicate node ids).
_SLUG_SYMBOLS = {"#": " sharp ", "+": " plus "}


def _slug(text: str) -> str:
    for sym, word in _SLUG_SYMBOLS.items():
        text = text.replace(sym, word)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "skill"


def _unique_id(base: str, seen: set[str]) -> str:
    """Guarantee a DOM/React-key-safe unique id, even if two distinct skills still slug
    to the same base (belt-and-suspenders beyond _SLUG_SYMBOLS). Deterministic: nodes
    are built in a stable frequency-descending order, so the -2/-3 suffixes are stable."""
    candidate, n = base, 2
    while candidate in seen:
        candidate, n = f"{base}-{n}", n + 1
    seen.add(candidate)
    return candidate


def _requirement_node(item: dict, classification: str, seen: set[str]) -> dict:
    """One job-ad-derived skill as a roadmap node carrying a `demand` badge payload.
    `seen` tracks ids already emitted so distinct skills never share a node id."""
    skill, pct, count, total = item["skill"], item["pct"], item["count"], item["total"]
    if classification == "required":
        node_type = "required"
        description = f"Required in {pct}% of job ads ({count} of {total} analyzed)."
    else:
        node_type = "good-to-know"
        description = f"Listed as an advantage in {pct}% of job ads ({count} of {total} analyzed)."
    return {
        "id": _unique_id(f"market-{_slug(skill)}", seen),
        "label": skill,
        "level": "intermediate",
        "type": node_type,
        "description": description,
        "resources": [],
        "demand": {"classification": classification, "count": count, "total": total, "pct": pct},
    }


def inject_requirements(roadmap: dict, requirements: dict | None) -> dict:
    """Append job-ad-derived skill nodes as their own pipeline stages: a separate
    'In Demand Now' (required) column and a 'Gives an Advantage' (advantage) column.

    Returns a NEW dict with a copied `sections` list — never mutates the input, because
    the static roadmap comes from load_roadmaps()'s @lru_cache and is shared across
    requests. Returns the roadmap unchanged when there are no requirements to show.
    """
    required = (requirements or {}).get("required", [])
    advantage = (requirements or {}).get("advantage", [])
    if not required and not advantage:
        return roadmap

    # One id namespace across both columns so no two market nodes ever collide.
    seen: set[str] = set()
    extra: list[dict] = []
    if required:
        extra.append({
            "id": "in-demand",
            "label": "In Demand Now",
            "source": "job_ads",
            "nodes": [_requirement_node(i, "required", seen) for i in required],
        })
    if advantage:
        extra.append({
            "id": "advantage",
            "label": "Gives an Advantage",
            "source": "job_ads",
            "nodes": [_requirement_node(i, "advantage", seen) for i in advantage],
        })
    return {**roadmap, "sections": [*roadmap.get("sections", []), *extra]}
