"""Requirement enrichment (DEV-59): frequency-based Required/Advantage classification."""
from collections import Counter

from app.services.requirements_service import (
    _display,
    _is_skill,
    classify_requirements,
)

# Small explicit vocab so the pure classifier tests don't depend on the real skill map.
_TEST_STOP = {"remote", "part-time"}


def _title(s: str) -> str:
    return s.title()


def _skill_ok(s: str) -> bool:
    return len(s) >= 2 and s not in _TEST_STOP


def _classify(counts, n_ads, **overrides):
    kwargs = dict(
        required_ratio=0.3,
        advantage_ratio=0.1,
        max_per_bucket=6,
        min_ads=8,
        is_skill=_skill_ok,
        display=_title,
    )
    kwargs.update(overrides)
    return classify_requirements(counts, n_ads, **kwargs)


def test_buckets_by_frequency_ratio():
    counts = Counter({"react": 40, "docker": 20, "redis": 5, "remote": 90})
    out = _classify(counts, 100)
    # react 40% -> required; docker 20% -> advantage; redis 5% -> dropped; remote filtered
    assert {e["skill"] for e in out["required"]} == {"React"}
    assert {e["skill"] for e in out["advantage"]} == {"Docker"}


def test_entry_shape_and_pct_math():
    out = _classify(Counter({"react": 31}), 50)
    entry = out["required"][0]
    assert entry == {"skill": "React", "count": 31, "total": 50, "pct": 62}


def test_stopword_and_junk_filtered_out():
    counts = Counter({"remote": 80, "part-time": 70, "react": 40})
    out = _classify(counts, 100)
    labels = {e["skill"] for e in out["required"] + out["advantage"]}
    assert labels == {"React"}


def test_empty_when_too_few_ads():
    out = _classify(Counter({"react": 4}), 4)  # n_ads < min_ads
    assert out == {"required": [], "advantage": []}


def test_empty_counter():
    assert _classify(Counter(), 100) == {"required": [], "advantage": []}


def test_caps_per_bucket():
    counts = Counter({f"skill{i}": 50 for i in range(10)})  # all 50% -> required
    out = classify_requirements(
        counts, 100,
        required_ratio=0.3, advantage_ratio=0.1, max_per_bucket=3, min_ads=8,
        is_skill=lambda s: True, display=_title,
    )
    assert len(out["required"]) == 3  # kept the top 3 by frequency, rest dropped


def test_default_skill_predicate_and_display_use_real_vocab():
    # The service's real defaults: employment noise is dropped, canonical casing applied.
    assert _is_skill("part-time") is False
    assert _is_skill("react") is True
    assert _display("typescript") == "TypeScript"  # from skill_aliases values
    assert _display("css") == "CSS"                 # from careers keySkills
    assert _display("someunknownskill") == "Someunknownskill"  # .title() fallback
