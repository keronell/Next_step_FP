"""Job-ad requirement enrichment (DEV-59).

Given a career, mine the job-ad corpus for the skills employers ask for in that
career's `field` and classify them by how often they appear across the field's ads:

  Required  = skill in >= required_ratio of the sampled ads   ("In demand — required")
  Advantage = skill in [advantage_ratio, required_ratio)       ("Gives an advantage")

Skills are already extracted + normalized to canonical (English) forms at ingestion
(data/scripts/extract_skills.py), so this is language-agnostic: a Hebrew ad and an
English ad both contribute their extracted skills to the same field-level count. The
classifier reads only those normalized skill tokens, never raw prose.

`classify_requirements` is a pure function (no I/O) so it is unit-tested directly.
`RequirementsService` wires it to the RAG store and never raises — any failure yields
an empty result so the roadmap request is never broken.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Callable

from common.config import Settings
from common.logging import get_logger
from common.data import load_careers

logger = get_logger(__name__)

# Shipped inside the common package (repo-root paths don't exist in containers).
import common.data as _common_data

_SKILL_ALIASES_PATH = Path(_common_data.__file__).resolve().parent / "skill_aliases.json"

# Employment/logistics, industry, and over-generic tokens that leak into the extracted
# `skills` lists (they come partly from raw job-board tags). Dropped so a badge never
# reads "Required in 60% of job ads: Digital Nomad". Any token that is also a curated
# career keySkill is protected below, so legit skills like "Strategy" are never stopped.
_RAW_STOPWORDS = {
    # employment type / logistics
    "part-time", "full-time", "part time", "full time", "contract", "freelance",
    "remote", "hybrid", "onsite", "on-site", "internship", "intern", "temporary",
    "permanent", "entry level", "entry-level", "senior", "junior", "mid", "lead",
    "nomad", "digital nomad", "relocation", "visa",
    # generic roles / functions (the real skill is a specific tool, not the role)
    "support", "customer support", "customer service", "recruitment", "hr", "admin",
    "administration", "operations", "sales", "marketing", "analyst", "consulting",
    "management", "manager", "developer", "engineer", "engineering", "designer",
    # industries / domains
    "growth", "financial", "finance", "fintech", "legal", "healthcare", "ecommerce",
    "e-commerce", "startup", "saas", "b2b", "b2c", "business", "content", "media",
    "video", "product", "project", "design", "strategy",
    # over-generic tech words
    "software", "development", "tech", "technology", "web", "app", "digital",
    "technical", "computer", "it", "english", "teamwork", "communication",
    "exec", "executive", "operational",
}

# Display-casing overrides for common tokens the shared alias map / keySkills miss
# (they are lowercased in the corpus). Everything else falls back to str.title().
_EXTRA_DISPLAY = {
    "html": "HTML", "css": "CSS", "sql": "SQL", "aws": "AWS", "gcp": "GCP",
    "api": "API", "rest api": "REST API", "ci/cd": "CI/CD", "ui/ux design": "UI/UX Design",
    "ux": "UX", "ui": "UI", "php": "PHP", "aws cloud": "AWS Cloud",
    # Some sources store multi-word skills concatenated; restore readable casing.
    "dataanalysis": "Data Analysis", "projectmanagement": "Project Management",
    "agilemethodology": "Agile Methodology", "bigdata": "Big Data",
}


@lru_cache
def _skill_display_map() -> dict[str, str]:
    """lowercased skill token -> canonical display casing. Sourced from the shared
    alias map (its values are canonical, e.g. "typescript" -> "TypeScript") plus the
    careers' keySkills (which give casing for CSS, APIs, CI/CD, ...). Anything not
    covered falls back to str.title() at lookup time."""
    m: dict[str, str] = dict(_EXTRA_DISPLAY)
    try:
        aliases = json.loads(_SKILL_ALIASES_PATH.read_text(encoding="utf-8")).get("aliases", {})
        for canonical in aliases.values():
            m[str(canonical).lower()] = str(canonical)
    except Exception:  # noqa: BLE001 - display casing is best-effort; .title() fallback
        logger.warning("could not load skill_aliases display map from %s", _SKILL_ALIASES_PATH, exc_info=True)
    for career in load_careers():
        for skill in career.get("keySkills", []):
            m[str(skill).lower()] = str(skill)
    return m


@lru_cache
def _keyskills_lower() -> frozenset[str]:
    return frozenset(s.lower() for c in load_careers() for s in c.get("keySkills", []))


@lru_cache
def _stopwords() -> frozenset[str]:
    # Never stop a curated keySkill (e.g. "strategy" is a Product Manager skill).
    return frozenset(_RAW_STOPWORDS - _keyskills_lower())


def _is_skill(token: str) -> bool:
    return len(token) >= 2 and token not in _stopwords()


def _display(token: str) -> str:
    return _skill_display_map().get(token, token.title())


def _empty() -> dict:
    return {"required": [], "advantage": []}


def classify_requirements(
    counts: Counter,
    n_ads: int,
    *,
    required_ratio: float,
    advantage_ratio: float,
    max_per_bucket: int,
    min_ads: int,
    is_skill: Callable[[str], bool],
    display: Callable[[str], str],
) -> dict:
    """Bucket skills into Required / Advantage by document frequency. Pure function.

    Returns {"required": [entry...], "advantage": [entry...]} where each entry is
    {"skill": <display>, "count": int, "total": n_ads, "pct": round(pct)}, ordered by
    frequency (descending) and capped to `max_per_bucket`. Empty when there are too few
    ads to be meaningful (n_ads < min_ads).
    """
    result = _empty()
    if n_ads < min_ads:
        return result

    for token, count in counts.most_common():  # most_common() is frequency-descending
        if not is_skill(token):
            continue
        ratio = count / n_ads
        if ratio >= required_ratio:
            bucket = "required"
        elif ratio >= advantage_ratio:
            bucket = "advantage"
        else:
            continue
        if len(result[bucket]) < max_per_bucket:
            result[bucket].append({
                "skill": display(token),
                "count": count,
                "total": n_ads,
                "pct": round(ratio * 100),
            })
    return result


class RequirementsService:
    """Mines the job-ad corpus for a career field's in-demand skills — the corpus
    lives in matching-service, reached via Dapr invocation. Never raises: any
    failure (matching down, sidecar off) yields an empty result and the roadmap
    request degrades to the plain roadmap, exactly the monolith contract."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def _field_skills(self, field: str, sample_size: int) -> tuple[Counter, int]:
        from urllib.parse import urlencode

        from common import dapr

        # field rides as a QUERY param: values like "UI / UX Design" can never
        # round-trip through a path segment (encoded slashes 404 on the callee).
        query = urlencode({"field": field, "sample_size": sample_size})
        r = dapr.invoke("matching", f"internal/field-skills?{query}", timeout=15.0)
        if r.status_code != 200:
            raise RuntimeError(f"matching field-skills answered {r.status_code}")
        body = r.json()
        return Counter(body["counts"]), body["n_ads"]

    def get_requirements(self, career_id: str) -> dict:
        try:
            field = next(
                (c["field"] for c in load_careers() if c["id"] == career_id), None
            )
            if not field:
                return _empty()
            s = self._settings
            counts, n_ads = self._field_skills(field, s.requirements_sample_size)
            return classify_requirements(
                counts,
                n_ads,
                required_ratio=s.requirements_required_ratio,
                advantage_ratio=s.requirements_advantage_ratio,
                max_per_bucket=s.requirements_max_per_bucket,
                min_ads=s.requirements_min_ads,
                is_skill=_is_skill,
                display=_display,
            )
        except Exception:  # noqa: BLE001 - never break a roadmap request over this
            logger.warning("requirement mining for %r failed", career_id, exc_info=True)
            return _empty()


class FakeRequirementsService:
    """Test double: returns a canned requirements dict without touching the RAG store."""

    def __init__(self, requirements: dict):
        self._requirements = requirements

    def get_requirements(self, career_id: str) -> dict:
        return self._requirements
