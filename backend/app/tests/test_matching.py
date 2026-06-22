"""Unit tests for the deterministic matching service."""
from collections import Counter

from app.data import load_careers
from app.repositories.career_repository import CareerCandidate
from app.services.matching_service import FORMULA_WEIGHTS, match

CAREERS = load_careers()
ANSWERS = {f"q{i}": (i % 4) for i in range(1, 11)}


def _candidate(career, sim=0.5, skills=None):
    return CareerCandidate(career, sim, skills if skills is not None else Counter())


def test_weights_sum_to_one():
    assert abs(sum(FORMULA_WEIGHTS.values()) - 1.0) < 1e-9


def test_scores_in_range_and_sorted():
    candidates = [_candidate(c, sim=0.5) for c in CAREERS]
    recs = match(ANSWERS, candidates)
    assert recs
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    for r in recs:
        assert 0.0 <= r["score"] <= 1.0


def test_missing_metadata_does_not_crash():
    # semantic_similarity None (no ads) and empty market skills must be handled.
    candidates = [CareerCandidate(c, None, Counter()) for c in CAREERS]
    recs = match(ANSWERS, candidates)
    assert recs
    for r in recs:
        assert r["score_breakdown"]["semantic_similarity"] == 0.0
        assert r["score_breakdown"]["skill_overlap"] == 0.0
        assert r["matched_skills"] == []


def test_duplicate_candidates_removed():
    frontend = CAREERS[0]
    candidates = [_candidate(frontend, sim=0.9), _candidate(frontend, sim=0.9)]
    recs = match(ANSWERS, candidates)
    assert len([r for r in recs if r["id"] == frontend["id"]]) == 1


def test_no_candidates_returns_empty():
    assert match(ANSWERS, []) == []


def test_skill_overlap_and_missing_skills():
    frontend = next(c for c in CAREERS if c["id"] == "frontend")
    market = Counter({"react": 5, "css": 3, "graphql": 4})  # react+css match keySkills
    recs = match(ANSWERS, [_candidate(frontend, sim=0.5, skills=market)])
    rec = recs[0]
    assert "React" in rec["matched_skills"]
    assert rec["score_breakdown"]["skill_overlap"] > 0
    # graphql is in-demand but not a listed key skill -> surfaced as missing/extra.
    assert "Graphql" in rec["missing_skills"]


def test_deterministic_tie_break_by_id():
    # Two careers identical except for id -> equal score -> sorted by id ascending.
    base = {
        "title": "X", "description": "d", "keySkills": ["A"], "icon": "I",
        "roadmapKey": "x", "field": "F",
        "weights": {f"q{i}": 1 for i in range(1, 11)}, "bonuses": [],
    }
    c_b = CareerCandidate({**base, "id": "bbb"}, 0.5, Counter())
    c_a = CareerCandidate({**base, "id": "aaa"}, 0.5, Counter())
    recs = match(ANSWERS, [c_b, c_a])
    assert [r["id"] for r in recs] == ["aaa", "bbb"]
