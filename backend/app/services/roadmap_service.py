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

from app.core.config import get_settings
from app.core.logging import get_logger
from app.data import load_careers, load_roadmaps

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


def _build_prompt(career_id: str, profile: str | None, missing_skills: list[str]) -> str:
    parts = [f"Build a learning roadmap for becoming a {_career_title(career_id)}."]
    if profile:
        parts.append(f"The learner describes themselves: {profile}")
    if missing_skills:
        parts.append(
            "Prioritize and weave in these skills they are currently missing: "
            + ", ".join(missing_skills)
            + "."
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


def _generate(career_id: str, profile: str | None, missing_skills: list[str], settings) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _build_prompt(career_id, profile, missing_skills)},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    return _validate(json.loads(resp.choices[0].message.content))


def get_roadmap(
    career_id: str,
    profile: str | None = None,
    missing_skills: list[str] | None = None,
) -> dict | None:
    """Personalized LLM roadmap when possible; static data/roadmaps.json otherwise.

    Falls back to static on: no OpenAI key, no personalization context, or any LLM
    error — so the endpoint always returns something the frontend can render.
    """
    static = load_roadmaps().get(career_id)
    settings = get_settings()
    if settings.openai_api_key and (profile or missing_skills):
        try:
            generated = _generate(career_id, profile, missing_skills or [], settings)
            logger.info("Generated LLM roadmap for %s", career_id)
            return generated
        except Exception:  # noqa: BLE001 - never fail the request over LLM problems
            logger.warning("LLM roadmap generation failed for %s; using static", career_id, exc_info=True)
    return static
