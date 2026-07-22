"""DEV-60: the self-input profile must genuinely move matching output, and a
skipped profile must change nothing at all."""
from collections import Counter

import pytest

from common.data import load_careers
from common.models.profile import ExperienceEntry, ProjectEntry, UserProfile
from common.profile_text import canonical_skills, profile_sentences
from app.repositories.career_repository import CareerCandidate
from app.services.matching_service import (
    FORMULA_WEIGHTS,
    PROFILE_WEIGHTS,
    _squash,
    match,
)
from app.services.profile import build_profile

CAREERS = load_careers()
ANSWERS = {f"q{i}": (i % 4) for i in range(1, 11)}

DATA_ANALYST = next(c for c in CAREERS if c["id"] == "data-analyst")


def _candidates(sim=0.5, skills=None):
    """One candidate per career, all with identical RAG signals — so any ranking
    change can only come from the profile."""
    return [
        CareerCandidate(c, sim, Counter(skills or {})) for c in CAREERS
    ]


def _by_id(recs):
    return {r["id"]: r for r in recs}


def test_both_weight_sets_sum_to_one():
    for weights in (FORMULA_WEIGHTS, PROFILE_WEIGHTS):
        assert abs(sum(weights.values()) - 1.0) < 1e-9


# ── skippable: no profile must be byte-identical to pre-DEV-60 ────────────────

@pytest.mark.parametrize("profile", [None, UserProfile()])
def test_skipped_profile_is_a_no_op(profile):
    baseline = match(ANSWERS, _candidates())
    assert match(ANSWERS, _candidates(), profile=profile) == baseline


def test_no_profile_keeps_the_original_model_version():
    for rec in match(ANSWERS, _candidates()):
        assert rec["model_version"] == "formula-v1"
        assert "user_skill_match" not in rec["score_breakdown"]


# ── the acceptance criterion: it measurably changes the output ────────────────

def test_profile_skills_raise_the_matching_career():
    """A profile full of a career's key skills must lift that career's score."""
    profile = UserProfile(skills=DATA_ANALYST["keySkills"])
    before = _by_id(match(ANSWERS, _candidates()))
    after = _by_id(match(ANSWERS, _candidates(), profile=profile))

    assert DATA_ANALYST["id"] in after, "the profiled career should reach the top 3"
    if DATA_ANALYST["id"] in before:
        assert after[DATA_ANALYST["id"]]["score"] > before[DATA_ANALYST["id"]]["score"]

    rec = after[DATA_ANALYST["id"]]
    assert rec["model_version"] == "formula-v1+profile"
    assert rec["score_breakdown"]["user_skill_match"] > 0


def test_profile_makes_matched_and_missing_skills_user_derived():
    """Roadmap.jsx renders matched_skills as 'you may already have this skill' —
    with a profile that must be literally true, and gaps must be real gaps."""
    have = DATA_ANALYST["keySkills"][:2]
    profile = UserProfile(skills=have)
    rec = _by_id(match(ANSWERS, _candidates(), profile=profile))[DATA_ANALYST["id"]]

    assert rec["matched_skills"] == have
    for skill in have:
        assert skill not in rec["missing_skills"]
    for skill in DATA_ANALYST["keySkills"][2:]:
        assert skill in rec["missing_skills"]


def test_matched_skills_drive_the_reason_text():
    profile = UserProfile(skills=DATA_ANALYST["keySkills"][:2])
    rec = _by_id(match(ANSWERS, _candidates(), profile=profile))[DATA_ANALYST["id"]]
    assert any("You already have 2 of the" in r for r in rec["reasons"])


def test_scores_stay_in_range_with_a_maximal_profile():
    profile = UserProfile(
        skills=sorted({s for c in CAREERS for s in c["keySkills"]})[:40],
        projects=[ProjectEntry(name="p", technologies=["React", "Python"])],
    )
    for rec in match(ANSWERS, _candidates(sim=1.0), profile=profile):
        assert 0.0 <= rec["score"] <= 1.0


# ── skill normalization ───────────────────────────────────────────────────────

def test_skills_are_canonicalized_and_include_project_technologies():
    profile = UserProfile(
        skills=["ReactJS", "  python3 "],
        projects=[ProjectEntry(name="Dash", technologies=["postgres"])],
    )
    assert canonical_skills(profile) == {"react", "python", "postgresql"}


def test_alias_spelling_scores_the_same_as_the_canonical_one():
    canonical = UserProfile(skills=["React", "TypeScript"])
    aliased = UserProfile(skills=["reactjs", "ts"])
    assert _by_id(match(ANSWERS, _candidates(), profile=canonical)) == _by_id(
        match(ANSWERS, _candidates(), profile=aliased)
    )


# ── experience-only profiles ──────────────────────────────────────────────────

EXPERIENCE_ONLY = UserProfile(
    experience=[
        ExperienceEntry(
            role="Data Analyst",
            context="a fintech",
            duration_months=24,
            description="built dashboards and SQL pipelines",
        )
    ]
)


def test_experience_only_profile_never_claims_market_skills_as_the_users():
    """No skill tags, but a real profile. Reporting market-derived matched_skills
    would tell them they already have skills they never entered."""
    # "sql" IS a data-analyst key skill, so the legacy path reports it as matched.
    market = {"sql": 4}
    rec = _by_id(match(ANSWERS, _candidates(skills=market)))[DATA_ANALYST["id"]]
    assert rec["matched_skills"] == ["SQL"]  # legacy path: market-derived

    rec = _by_id(match(ANSWERS, _candidates(skills=market), profile=EXPERIENCE_ONLY))[
        DATA_ANALYST["id"]
    ]
    assert rec["matched_skills"] == []
    assert rec["missing_skills"][: len(DATA_ANALYST["keySkills"])] == DATA_ANALYST["keySkills"]
    assert rec["model_version"] == "formula-v1+profile"


def test_experience_only_profile_does_not_deflate_every_score():
    """user_skill_match would be 0 for all 16 careers — subtracting 0.20 everywhere
    changes no ranking and just makes every percentage look worse."""
    baseline = _by_id(match(ANSWERS, _candidates()))
    with_exp = _by_id(match(ANSWERS, _candidates(), profile=EXPERIENCE_ONLY))
    for cid, rec in with_exp.items():
        if cid in baseline:
            assert rec["score"] == baseline[cid]["score"]
        assert "user_skill_match" not in rec["score_breakdown"]


# ── English-only pipeline ─────────────────────────────────────────────────────

def test_non_latin_text_is_dropped_rather_than_embedded():
    """The catalog, corpus and MiniLM are all English — non-Latin input has nothing
    to match against, and embedding it degrades the vector instead of helping."""
    profile = UserProfile(
        experience=[ExperienceEntry(role="מפתחת תוכנה", context="סטארטאפ")],
        skills=["פייתון", "reactjs"],
        projects=[ProjectEntry(name="לוח מחוונים", technologies=["postgres"])],
    )
    text = build_profile(ANSWERS, profile)
    assert not any("֐" <= ch <= "׿" for ch in text)
    assert "I know react." in text          # canonicalized, kept
    assert "using postgresql" in text       # kept even though the project name went


def test_untranslatable_tags_do_not_engage_the_profile_weights():
    """A tag we can't compare against the English catalog is not a skill signal.
    Counting it switched on PROFILE_WEIGHTS and handed 20% of the score to a
    user_skill_match that could only ever be 0 — deflating every match percentage."""
    unusable = UserProfile(skills=["פייתון"])
    assert canonical_skills(unusable) == set()

    baseline = _by_id(match(ANSWERS, _candidates(skills={"sql": 4})))
    with_tag = _by_id(match(ANSWERS, _candidates(skills={"sql": 4}), profile=unusable))
    for cid, rec in with_tag.items():
        assert rec["score"] == baseline[cid]["score"]
        assert "user_skill_match" not in rec["score_breakdown"]


def test_english_prose_does_reach_the_embedding_query():
    profile = UserProfile(
        experience=[ExperienceEntry(role="Data Analyst", context="a fintech", duration_months=24)]
    )
    text = build_profile(ANSWERS, profile)
    assert "I worked as Data Analyst at a fintech for 2 years." in text
    assert profile_sentences(None) == []


# ── spelling / spacing ────────────────────────────────────────────────────────

def test_spacing_variants_are_one_skill():
    """The corpus writes "powerbi", the catalog writes "Power BI". Without squashing,
    a user who types either gets no credit and the gap list shows both spellings."""
    for spelling in ("Power BI", "powerbi", "power  bi", "PowerBI"):
        rec = _by_id(
            match(
                ANSWERS,
                _candidates(skills={"powerbi": 4}),
                profile=UserProfile(skills=[spelling]),
            )
        )[DATA_ANALYST["id"]]
        assert "Power BI" in rec["matched_skills"], spelling
        assert "Power BI" not in rec["missing_skills"], spelling
        # The market's spelling must never appear beside the curated one.
        assert not any(_squash(m) == "powerbi" for m in rec["missing_skills"]), spelling


def test_cpp_and_csharp_stay_distinct():
    assert _squash("C++") != _squash("C#")


# ── learned-model path ────────────────────────────────────────────────────────

def test_model_path_derives_gaps_from_the_profile_too():
    """MATCHER_MODEL_PATH is a supported deployment. Leaving matched/missing
    market-derived there would tell a profile user they lack skills they entered."""
    from test_matching_with_model import make_model

    have = DATA_ANALYST["keySkills"][:2]
    recs = match(
        ANSWERS,
        _candidates(),
        model=make_model(DATA_ANALYST["id"]),
        profile=UserProfile(skills=have),
    )
    rec = _by_id(recs)[DATA_ANALYST["id"]]

    assert rec["model_version"] == "test-model-v0"  # still the model's score
    assert rec["matched_skills"] == have
    for skill in have:
        assert skill not in rec["missing_skills"]
    assert any("You already have 2 of the" in r for r in rec["reasons"])


# ── market-skill counting ─────────────────────────────────────────────────────

def test_repository_unions_overlapping_market_sources(monkeypatch):
    """build_rag.py upserts the SAME jobs list into both Chroma and Postgres, so
    summing the two counters let one ad masquerade as two — enough to clear
    MIN_MARKET_MENTIONS and count as real employer demand."""
    from common.config import get_settings
    from app.repositories import career_repository as repo_mod

    class _Rag:
        count = 1

        def encode(self, text):
            return [0.0]

        def query_field(self, embedding, field, k):
            return 0.5, Counter({"kubernetes": 1, "sql": 4})

    monkeypatch.setattr(
        repo_mod.job_postings_service,
        "skill_counts",
        lambda field, k: Counter({"kubernetes": 1, "sql": 3}),
    )
    market = repo_mod.CareerRepository(_Rag(), get_settings()).get_candidates(ANSWERS)[0].market_skills
    assert market["kubernetes"] == 1  # one ad, seen twice
    assert market["sql"] == 4         # genuinely common: max, not 7


def test_a_single_ad_is_not_a_strong_market_skill():
    from app.services.matching_service import _strong_market_skills

    one_ad = CareerCandidate(DATA_ANALYST, 0.5, Counter({"kubernetes": 1, "sql": 4}))
    assert _strong_market_skills(one_ad) == {"sql"}


# ── validation at the trust boundary ──────────────────────────────────────────

def test_entry_and_skill_caps_are_enforced():
    profile = UserProfile(skills=[f"skill-{i}" for i in range(100)])
    assert len(profile.skills) == 40

    with pytest.raises(ValueError):
        UserProfile(projects=[ProjectEntry(name=str(i)) for i in range(11)])


def test_blank_and_duplicate_skills_are_dropped():
    profile = UserProfile(skills=["Python", "  ", "python", "SQL"])
    assert profile.skills == ["Python", "SQL"]


@pytest.mark.parametrize("blank", ["   ", "\t", "\n "])
def test_whitespace_only_required_fields_are_rejected(blank):
    """min_length counts whitespace, so role="   " validated — and an entry that
    contributes nothing still flipped is_empty, stamping the profile path."""
    with pytest.raises(ValueError):
        ExperienceEntry(role=blank)
    with pytest.raises(ValueError):
        ProjectEntry(name=blank)


def test_optional_fields_are_stripped():
    entry = ExperienceEntry(role="  Data Analyst  ", context=" a fintech ")
    assert entry.role == "Data Analyst"
    assert entry.context == "a fintech"
