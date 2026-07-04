"""Unit tests for the shared learned-matcher feature assembly."""
from collections import Counter

from app.data import load_careers
from app.services import feature_builder as fb
from app.services.matching_service import _raw_fit

CAREERS = load_careers()
ANSWERS = {qid: (i % 4) for i, qid in enumerate(fb.QUESTION_IDS, start=1)}


def test_vector_matches_names_and_length():
    names = fb.feature_names(CAREERS)
    vec = fb.build_feature_vector(ANSWERS, CAREERS, {}, {})
    n_q = len(fb.QUESTION_IDS)
    assert len(vec) == len(names) == 2 * n_q + 3 * len(CAREERS)


def test_missing_and_null_answers_masked():
    answers = {"q1": 2, "q2": None}  # q3..q10 absent (branched away / not asked)
    vec = fb.build_feature_vector(answers, CAREERS, {}, {})
    names = fb.feature_names(CAREERS)
    at = {n: v for n, v in zip(names, vec)}
    assert at["q1"] == 2.0 and at["q1_present"] == 1.0
    assert at["q2"] == 0.0 and at["q2_present"] == 0.0
    assert at["q3"] == 0.0 and at["q3_present"] == 0.0


def test_fit_matches_matching_service_math():
    # feature_builder.raw_fit must stay identical to matching_service._raw_fit.
    for career in CAREERS:
        assert fb.raw_fit(career, ANSWERS) == _raw_fit(career, ANSWERS)


def test_fit_normalized_to_best_career():
    fits = fb.questionnaire_fits(CAREERS, ANSWERS)
    assert max(fits.values()) == 1.0
    assert all(0.0 <= v <= 1.0 for v in fits.values())


def test_semantic_none_degrades_to_zero():
    semantic = {c["id"]: None for c in CAREERS}
    vec = fb.build_feature_vector(ANSWERS, CAREERS, semantic, {})
    names = fb.feature_names(CAREERS)
    sem_values = [v for n, v in zip(names, vec) if n.endswith("_sem")]
    assert sem_values == [0.0] * len(CAREERS)


def test_skill_overlap_counts_matches():
    frontend = next(c for c in CAREERS if c["id"] == "frontend")
    market = Counter({"react": 5, "css": 3, "graphql": 4})
    overlap = fb.skill_overlap(frontend, market)
    assert overlap == 2 / len(frontend["keySkills"])  # react + css
    assert fb.skill_overlap(frontend, Counter()) == 0.0
