"""Turn a self-input UserProfile into the two things the pipeline can actually
consume (DEV-60).

    profile_sentences(p)  -> natural-language sentences, appended to the
                             questionnaire profile before it is embedded
    canonical_skills(p)   -> lowercased canonical skill tokens, compared against
                             career keySkills and market demand

**This feature is English-only.** The career catalog, the job-ad corpus, the alias
map and the embedding model (all-MiniLM-L6-v2, uncased English) are all English, so
there is nothing for non-English input to match against.

_usable_text is therefore input hygiene, not translation: non-Latin prose is
dropped rather than embedded, because MiniLM maps it to a meaningless region of the
vector space and would actively degrade the user's match instead of merely failing
to help it. Tags are canonicalized through skill_aliases.json first, so "reactjs"
and "React" both survive as "react".
"""
from __future__ import annotations

from common.data import load_skill_aliases
from common.models.profile import UserProfile

# Share of a string's letters that must be ASCII for it to be worth embedding.
_MIN_LATIN_RATIO = 0.6


def _usable_text(text: str) -> bool:
    """English-only pipeline: text we cannot embed meaningfully is skipped."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if c.isascii())
    return latin / len(letters) >= _MIN_LATIN_RATIO


def _duration_phrase(months: int | None) -> str:
    if not months:
        return ""
    if months >= 12:
        years = months // 12
        return f" for {years} year{'s' if years > 1 else ''}"
    return f" for {months} month{'s' if months > 1 else ''}"


def canonical_skill(raw: str) -> str:
    """One skill token in its canonical lowercase form (via skill_aliases.json).

    Lowercase because every consumer compares lowercased: matching against
    career keySkills and against the market-skill Counter, both of which are
    lowercased at their own boundaries.
    """
    token = str(raw).strip().lower()
    return load_skill_aliases().get(token, token)


def _embeddable_tags(tags: list[str]) -> list[str]:
    """Canonical, Latin-script tag spellings for the embedding query, order kept.

    Lowercase is fine (and dedupes "React"/"reactjs"): all-MiniLM-L6-v2 is uncased.
    """
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        canonical = canonical_skill(tag)
        if not canonical or canonical in seen or not _usable_text(canonical):
            continue
        seen.add(canonical)
        out.append(canonical)
    return out


def canonical_skills(profile: UserProfile | None) -> set[str]:
    """Everything the user claims to know: the Skills section plus the
    technologies listed on their projects.

    Shares _embeddable_tags with the prose builder ON PURPOSE. When the two had
    separate notions of a usable tag they disagreed: an untranslatable tag was
    dropped from the embedding but kept here, so the profile produced a
    baseline-identical query while still switching on PROFILE_WEIGHTS — handing 20%
    of the score to a user_skill_match that could only ever be 0, and knocking up to
    20 points off every displayed match percentage.
    """
    if profile is None:
        return set()
    raw = list(profile.skills)
    for project in profile.projects:
        raw.extend(project.technologies)
    return set(_embeddable_tags(raw))


def profile_sentences(profile: UserProfile | None) -> list[str]:
    """First-person sentences describing the profile, matching the voice of
    build_profile's questionnaire sentences ("I am ...")."""
    if profile is None or profile.is_empty:
        return []

    out: list[str] = []

    for exp in profile.experience:
        if not _usable_text(exp.role):
            continue
        sentence = f"I worked as {exp.role}"
        if exp.context and _usable_text(exp.context):
            sentence += f" at {exp.context}"
        sentence += _duration_phrase(exp.duration_months)
        if exp.description and _usable_text(exp.description):
            sentence += f", where I {exp.description.rstrip('.')}"
        out.append(sentence + ".")

    for proj in profile.projects:
        parts = []
        if _usable_text(proj.name):
            parts.append(f"I built {proj.name}")
            if proj.description and _usable_text(proj.description):
                parts.append(f"a project where I {proj.description.rstrip('.')}")
        techs = _embeddable_tags(proj.technologies)
        if techs:
            # Canonical English, so safe to state even when the project name was dropped.
            joined = ", ".join(techs)
            parts.append(f"using {joined}" if parts else f"I have built projects using {joined}")
        if parts:
            out.append(", ".join(parts) + ".")

    skills = _embeddable_tags(profile.skills)
    if skills:
        out.append("I know " + ", ".join(skills) + ".")

    return out
