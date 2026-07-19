"""Phase 0 of the matching-module rework: synthetic silver labels from a local LLM panel.

Labels questionnaire profiles (real ones exported from public.submissions plus
generated synthetic ones) with multiple synthetic expert personas via local Ollama.
The labels are SILVER labels — LLM-generated, not expert ground truth.

Voting is two-stage (panel-v2.0.0): a deterministic stage 1 shortlists the q2
family's careers plus the q18-only careers, and the LLM stage 2 disambiguates
within that shortlist anchored on the tie-breaker answers (q14-q17/q18) and the
option->career key derived from careers.json bonuses. A single-pass 16-way vote
remains as the fallback when q2 was skipped. Rationale + Gate-0 numbers in the
comment above candidate_ids().

Outputs (data/training/):
    silver_labels.parquet          high-consensus profiles + panel votes + metadata
    ambiguous_labels.parquet       low-agreement profiles (excluded from training)
    archetypes_synthetic.parquet   per-persona ideal-candidate answers per career
    synthetic_agreement_report.md  Fleiss/pairwise kappa, distributions, Gate 0 checklist
    panel_votes.jsonl              raw vote log (append-only; enables resume)

Usage:
    python data/scripts/panel_label_profiles.py                   # full run
    python data/scripts/panel_label_profiles.py --limit 3         # smoke test
    python data/scripts/panel_label_profiles.py --aggregate-only  # recompute outputs from vote log
"""
from __future__ import annotations

import argparse
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

from dataset_guards import MIN_LABELS_PER_CAREER

# ---------------------------------------------------------------- configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b-instruct"
TEMPERATURE = 0.2  # fallback; personas carry their own (see PERSONAS)
NUM_PREDICT = 300
# v1.2.0: career count/coaching derived from the catalog (16 careers), no hardcoded six.
# v1.3.0: 18-question bank (q14-q18 discriminators) — profiles/archetypes rendered under
# the old bank must not resume or aggregate into this generation (resume and aggregate
# are scoped to PROMPT_VERSION, so any bank/catalog change needs a bump like this one).
# v2.0.0: two-stage voting (deterministic q2 family shortlist + keyed tie-breaker
# stage 2); single-pass 16-way retained only as the q2-skipped fallback.
# v2.1.0: coverage-guaranteed generation (pinned-cue seeded quotas + closed-loop
# top-up). The prompt is unchanged, but syn_NNNN profile ids are reused with
# different answers, so prior-generation votes must not resume into this one.
PROMPT_VERSION = "panel-v2.1.0"
LABEL_SOURCE = "synthetic_llm"
MAX_RETRIES = 2
WORKERS = 4
TIMEOUT_S = 120

N_SYNTHETIC_PROFILES = 200
RANDOM_SEED = 42
CONSENSUS_MIN_VOTES = 2  # of the 3 personas

QUESTIONS_JSON = Path("services/common/data/questions.json")
CAREERS_JSON = Path("services/common/data/careers.json")

# Single source of truth for the question set — derived from the bank, never
# hardcoded, so new questions (e.g. q11+) flow into synthetic profiles and
# archetypes automatically. Mirrors feature_builder.QUESTION_IDS on the serving side.
_QUESTION_BANK = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
QUESTION_IDS = [q["id"] for q in _QUESTION_BANK]
# Career universe, same principle: derived from the catalog in catalog order.
_CAREER_CATALOG = json.loads(CAREERS_JSON.read_text(encoding="utf-8"))
CAREER_IDS = [c["id"] for c in _CAREER_CATALOG]
TRAINING_DIR = Path("data/training")
REAL_PROFILES_JSON = TRAINING_DIR / "real_profiles.json"
VOTES_JSONL = TRAINING_DIR / "panel_votes.jsonl"
ARCHETYPES_JSONL = TRAINING_DIR / "panel_archetypes.jsonl"
SILVER_PARQUET = TRAINING_DIR / "silver_labels.parquet"
AMBIGUOUS_PARQUET = TRAINING_DIR / "ambiguous_labels.parquet"
ARCHETYPES_PARQUET = TRAINING_DIR / "archetypes_synthetic.parquet"
REPORT_MD = TRAINING_DIR / "synthetic_agreement_report.md"

# (persona_id, description, temperature). Temperatures differ per persona to break
# the same-base-model clone effect observed at panel-v1.0.1 (Fleiss kappa 0.93).
PERSONAS = [
    ("hiring_manager", "a senior engineering hiring manager with 15 years of experience interviewing candidates across software disciplines", 0.2),
    ("career_counselor", "a career counselor who specializes in guiding newcomers into technology careers", 0.6),
    ("bootcamp_instructor", "a coding-bootcamp instructor who has watched hundreds of beginners discover which tech track fits them", 0.9),
]

# Branch rules derived from the bank's declarative show_if (mirrors visibleQuestions
# in frontend/src/data.js). Previously hand-coded lambdas for q3/q9 only, which
# silently drifted when the q14-q17 family follow-ups landed — derived rules make
# that impossible: any gated question in questions.json is gated here too.
BRANCH_RULES = {
    q["id"]: (lambda a, cond=q["show_if"]: a.get(cond["q"]) in cond["in"])
    for q in _QUESTION_BANK if "show_if" in q
}

# Hand-built seed answer vectors per career (option semantics, not weight argmax).
# Branching is re-derived after perturbation, so branch-gated slots (q3/q9 and the
# q14-q17 family follow-ups) are only used when visible under the seed's q2 answer;
# hidden slots still carry an on-theme value for when perturbation flips q2.
# q11-q18 are the discriminator questions (bonus-only); seeding them with each
# career's on-theme option keeps the strongest synthetic profiles from putting noise
# on exactly the answers that separate the careers. Reached family slots and q18
# mirror the DoD archetypes in backend/app/tests/test_question_bank.py (each
# validated to rank its career #1 on raw questionnaire fit) — including the two
# deliberate None skips (product-manager on q16, technical-writer on q15: every
# option there boosts a rival, and skipping is a first-class answer). game-dev and
# ai-engineer q2 follow the archetypes' branch moves (1->0 and 1->2) so each seed
# reaches its own discriminator question.
CAREER_SEEDS = {
    "frontend":           {"q1": 2, "q2": 0, "q3": 1, "q4": 0, "q5": 1, "q6": 0, "q7": 1, "q8": 1, "q9": 3, "q10": 0, "q11": 0, "q12": 2, "q13": 0, "q14": 0, "q15": 0, "q16": 0, "q17": 0, "q18": 2},
    "backend":            {"q1": 3, "q2": 1, "q3": 2, "q4": 1, "q5": 1, "q6": 1, "q7": 1, "q8": 1, "q9": 1, "q10": 1, "q11": 1, "q12": 2, "q13": 1, "q14": 0, "q15": 3, "q16": 1, "q17": 0, "q18": 3},
    # q4/q6 follow the DoD archetype: the pre-16-catalog values (q4:2, q6:2) hit
    # data-analyst's bonuses and made this seed rank data-analyst #1, not data-science.
    "data-science":       {"q1": 2, "q2": 2, "q3": 3, "q4": 1, "q5": 2, "q6": 1, "q7": 2, "q8": 2, "q9": 0, "q10": 2, "q11": 2, "q12": 3, "q13": 2, "q14": 0, "q15": 0, "q16": 1, "q17": 0, "q18": 0},
    "devops":             {"q1": 2, "q2": 3, "q3": 2, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 3, "q9": 0, "q10": 3, "q11": 3, "q12": 2, "q13": 3, "q14": 0, "q15": 3, "q16": 0, "q17": 0, "q18": 0},
    "product-manager":    {"q1": 0, "q2": 2, "q3": 2, "q4": 2, "q5": 0, "q6": 0, "q7": 0, "q8": 0, "q9": 2, "q10": 0, "q11": 2, "q12": 0, "q13": 0, "q14": 3, "q15": 1, "q16": None, "q17": 2, "q18": 1},
    "ux-designer":        {"q1": 1, "q2": 0, "q3": 0, "q4": 0, "q5": 0, "q6": 0, "q7": 0, "q8": 0, "q9": 3, "q10": 0, "q11": 0, "q12": 1, "q13": 0, "q14": 3, "q15": 0, "q16": 0, "q17": 0, "q18": 0},
    "fullstack":          {"q1": 3, "q2": 1, "q3": 1, "q4": 0, "q5": 1, "q6": 2, "q7": 1, "q8": 1, "q9": 1, "q10": 1, "q11": 1, "q12": 2, "q13": 1, "q14": 0, "q15": 0, "q16": 0, "q17": 0, "q18": 3},
    "mobile":             {"q1": 3, "q2": 0, "q3": 2, "q4": 0, "q5": 1, "q6": 1, "q7": 1, "q8": 1, "q9": 2, "q10": 0, "q11": 0, "q12": 2, "q13": 0, "q14": 1, "q15": 0, "q16": 0, "q17": 0, "q18": 2},
    "data-analyst":       {"q1": 1, "q2": 2, "q3": 3, "q4": 2, "q5": 2, "q6": 2, "q7": 2, "q8": 2, "q9": 2, "q10": 2, "q11": 2, "q12": 3, "q13": 2, "q14": 0, "q15": 0, "q16": 0, "q17": 0, "q18": 0},
    "machine-learning":   {"q1": 3, "q2": 2, "q3": 3, "q4": 1, "q5": 1, "q6": 1, "q7": 2, "q8": 2, "q9": 1, "q10": 1, "q11": 2, "q12": 2, "q13": 1, "q14": 0, "q15": 3, "q16": 2, "q17": 0, "q18": 0},
    "ai-engineer":        {"q1": 3, "q2": 2, "q3": 2, "q4": 0, "q5": 1, "q6": 1, "q7": 2, "q8": 1, "q9": 1, "q10": 0, "q11": 2, "q12": 2, "q13": 1, "q14": 0, "q15": 0, "q16": 3, "q17": 0, "q18": 0},
    "cyber-security":     {"q1": 2, "q2": 3, "q3": 2, "q4": 3, "q5": 3, "q6": 1, "q7": 2, "q8": 3, "q9": 0, "q10": 3, "q11": 3, "q12": 3, "q13": 3, "q14": 0, "q15": 2, "q16": 0, "q17": 1, "q18": 0},
    "qa-engineer":        {"q1": 2, "q2": 1, "q3": 1, "q4": 3, "q5": 1, "q6": 1, "q7": 1, "q8": 1, "q9": 1, "q10": 1, "q11": 1, "q12": 3, "q13": 3, "q14": 0, "q15": 2, "q16": 0, "q17": 3, "q18": 0},
    "game-dev":           {"q1": 3, "q2": 0, "q3": 1, "q4": 0, "q5": 1, "q6": 1, "q7": 1, "q8": 1, "q9": 3, "q10": 0, "q11": 0, "q12": 2, "q13": 1, "q14": 2, "q15": 0, "q16": 0, "q17": 0, "q18": 2},
    "technical-writer":   {"q1": 1, "q2": 1, "q3": 1, "q4": 2, "q5": 2, "q6": 2, "q7": 0, "q8": 0, "q9": 2, "q10": 0, "q11": 0, "q12": 0, "q13": 0, "q14": 3, "q15": None, "q16": 0, "q17": 0, "q18": 0},
    "software-architect": {"q1": 3, "q2": 1, "q3": 2, "q4": 1, "q5": 3, "q6": 3, "q7": 1, "q8": 1, "q9": 0, "q10": 1, "q11": 3, "q12": 0, "q13": 1, "q14": 0, "q15": 1, "q16": 0, "q17": 2, "q18": 0},
}

# Seeds drive 60% of synthetic profiles (30% perturbed + 30% blended), so a career
# missing here gets almost no seeded representation in training data. Fail loudly on
# any catalog/bank drift instead of silently regenerating that bias.
if list(CAREER_SEEDS) != CAREER_IDS:
    raise SystemExit(
        "CAREER_SEEDS out of sync with careers.json (must list the same careers in "
        f"catalog order): missing={sorted(set(CAREER_IDS) - set(CAREER_SEEDS))} "
        f"extra={sorted(set(CAREER_SEEDS) - set(CAREER_IDS))}"
    )
for _cid, _seed in CAREER_SEEDS.items():
    if set(_seed) != set(QUESTION_IDS):
        raise SystemExit(
            f"CAREER_SEEDS[{_cid!r}] out of sync with questions.json: "
            f"missing={sorted(set(QUESTION_IDS) - set(_seed))} "
            f"extra={sorted(set(_seed) - set(QUESTION_IDS))}"
        )


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_catalog() -> tuple[list[dict], list[dict]]:
    questions = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    careers = json.loads(CAREERS_JSON.read_text(encoding="utf-8"))
    return questions, careers


# ---------------------------------------------------------------- profile generation
# Coverage design (root-cause analysis, 2026-07-18): noise 0.35 destroys a career's
# discriminator (q2 route + tie-breaker answer) in ~51% of seeded profiles, the
# 30%-seeded slice holds only ~3.75 profiles per career, and the two q18-only
# careers have a 0% answer-key share on random profiles — so the old mix could not
# guarantee the >= MIN_LABELS_PER_CAREER silver labels the Phase 1-3 guard demands.
# Fixes: (a) every career gets a guaranteed MIN_SEEDED_PER_CAREER seeded quota with
# its defining cues PINNED during perturbation (all other answers keep full noise —
# the seeded slice exists to provide strong exemplars, so noise must not erase the
# one answer that defines them); (b) main() closes the loop with bounded label-count
# top-up rounds, because label counts ultimately depend on the panel (game-dev's
# intact-signal consensus rate is ~10%, a protocol ceiling volume must compensate for).
MIN_SEEDED_PER_CAREER = 6
SEED_NOISE = 0.35
TOPUP_BATCH = 10        # pinned-cue profiles per starved career per coverage round
MAX_TOPUP_ROUNDS = 10


def apply_branching(answers: dict) -> dict:
    """Keep only questions visible under the adaptive path (mirrors visibleQuestions)."""
    out = {}
    for qid in QUESTION_IDS:
        if qid not in answers:
            continue
        rule = BRANCH_RULES.get(qid)
        if rule is not None and not rule(answers):
            continue
        out[qid] = answers[qid]
    return out


def pinned_qids(cid: str) -> frozenset[str]:
    """Answers that make a seeded profile recognizably its career: q2 plus the
    family tie-breaker for gated careers, the linear tie-breaker(s) for the rest."""
    career = next(c for c in _CAREER_CATALOG if c["id"] == cid)
    gated = {r["qId"] for r in career["bonuses"] if r["qId"] in _GATED_QIDS and r["bonus"] >= 3}
    if gated:
        return frozenset(gated | {"q2"})
    return frozenset(r["qId"] for r in career["bonuses"] if r["qId"] in LINEAR_DISCRIMINATORS)


def perturb_seed(seed_answers: dict, rng: random.Random, noise: float,
                 pinned: frozenset = frozenset()) -> dict:
    answers = {}
    for qid in QUESTION_IDS:
        val = seed_answers.get(qid, rng.randint(0, 3))
        if qid not in pinned:
            if rng.random() < noise:
                val = rng.randint(0, 3)
            if rng.random() < 0.05:  # occasional skip, like real users
                val = None
        answers[qid] = val
    return apply_branching(answers)


def generate_synthetic_profiles(n: int, rng: random.Random) -> list[dict]:
    career_ids = list(CAREER_SEEDS)
    profiles = []

    def perturb(seed_answers, noise, pinned=frozenset()):
        return perturb_seed(seed_answers, rng, noise, pinned)

    # Guaranteed pinned-cue quota per career; blended and random slices shrink as
    # needed so the requested total is always honored exactly. Below the quota
    # floor no valid mix exists — reject rather than silently over-generate.
    quota_floor = MIN_SEEDED_PER_CAREER * len(career_ids)
    if n < quota_floor:
        raise SystemExit(
            f"--n-synthetic {n} is below the coverage floor: the guaranteed seeded "
            f"quota alone needs {MIN_SEEDED_PER_CAREER} x {len(career_ids)} = "
            f"{quota_floor} profiles."
        )
    n_seeded = max(int(n * 0.3), quota_floor)
    n_mixed = min(int(n * 0.3), n - n_seeded)
    n_random = n - n_seeded - n_mixed

    for i in range(n_seeded):
        cid = career_ids[i % len(career_ids)]
        profiles.append(perturb(CAREER_SEEDS[cid], noise=SEED_NOISE, pinned=pinned_qids(cid)))
    for _ in range(n_mixed):
        a, b = rng.sample(career_ids, 2)
        blended = {qid: (CAREER_SEEDS[a] if rng.random() < 0.5 else CAREER_SEEDS[b]).get(qid)
                   for qid in QUESTION_IDS}
        profiles.append(perturb(blended, noise=0.20))
    for _ in range(n_random):
        answers = {qid: rng.randint(0, 3) for qid in QUESTION_IDS}
        profiles.append(perturb(answers, noise=0.0))

    return [
        {"profile_id": f"syn_{i:04d}", "profile_source": "synthetic", "answers": p}
        for i, p in enumerate(profiles)
    ]


def load_profiles(n_synthetic: int) -> list[dict]:
    real = json.loads(REAL_PROFILES_JSON.read_text(encoding="utf-8")) if REAL_PROFILES_JSON.exists() else []
    rng = random.Random(RANDOM_SEED)
    return real + generate_synthetic_profiles(n_synthetic, rng)


# ---------------------------------------------------------------- prompts
def render_profile(answers: dict, questions: list[dict]) -> str:
    lines = []
    for q in questions:
        qid = q["id"]
        if qid not in answers:
            lines.append(f"- {q['text']} -> (not asked; the adaptive questionnaire skipped it)")
            continue
        val = answers[qid]
        if val is None:
            lines.append(f"- {q['text']} -> (user skipped this question)")
        else:
            lines.append(f"- {q['text']} -> \"{q['options'][int(val)]}\"")
    return "\n".join(lines)


def render_careers(careers: list[dict]) -> str:
    return "\n".join(f"- {c['id']}: {c['title']} — {c['description']}" for c in careers)


def build_label_prompt(persona_desc: str, profile_text: str, careers: list[dict]) -> str:
    career_ids = json.dumps([c["id"] for c in careers])
    return f"""You are {persona_desc}.
You are reviewing one beginner's answers to a career-orientation questionnaire and must
recommend which tech career fits them best. Answer only as that expert persona.

The {len(careers)} possible careers:
{render_careers(careers)}

All {len(careers)} careers are equally valid outcomes — do not default to developer roles.
Some are not primarily coding careers: someone who leans toward visual design and
user empathy but not writing code may fit ux-designer better than frontend, someone
drawn to shaping vision, talking to users, and rallying teams rather than building
may fit product-manager best, and someone who loves explaining technology in plain
language may fit technical-writer over any developer role. Recommend the career the
answers actually support.

The person's questionnaire answers:
{profile_text}

Return STRICT JSON ONLY with this exact schema:
{{
  "top1": "career id",
  "top2": "career id or null",
  "confidence": 0.0,
  "explanation": "string"
}}

Rules:
1) "top1" is required and must be one of: {career_ids}
2) Always provide "top2" — your second-best fit from the same list, different from top1.
   Use null only if no other career is remotely plausible.
3) "confidence" is your confidence in top1, a number in [0, 1].
4) "explanation" is 1-2 short sentences citing the answers that drove your choice.
""".strip()


# ---------------------------------------------------------------- two-stage voting
# Stage 1 is deterministic: q2 is the product's own family router (it gates the
# q14-q17 family follow-ups), so the candidate shortlist is that family plus the
# careers whose only discriminator is the ungated q18 — those must stay reachable
# from every branch. Stage 2 is the LLM vote, over the shortlist only, anchored on
# the tie-breaker answers plus the option->career key the bank encodes as bonuses.
# Gate-0 result vs single-pass 16-way (48-profile pool, 3-persona qwen2.5:7b):
# newer-10 careers 22/30 vs 1/30 correct consensus, original six unchanged (11/18);
# with the discriminator signal intact in the profile, 33/34.
#
# Everything here is DERIVED from questions.json/careers.json (family = careers
# with a bonus on the branch's follow-up question; key = those bonuses), so bank
# and catalog changes flow through without edits — only PROMPT_VERSION must bump.

# q2 answer -> its family follow-up question id (the single-value show_if gates).
GATED_BY_Q2 = {
    q["show_if"]["in"][0]: q["id"]
    for q in _QUESTION_BANK
    if q.get("show_if", {}).get("q") == "q2" and len(q["show_if"]["in"]) == 1
}
_GATED_QIDS = set(GATED_BY_Q2.values())
# Careers with no family follow-up home — their discriminator must be linear
# (currently product-manager and technical-writer via q18).
_UNGATED_CAREER_IDS = {
    c["id"] for c in _CAREER_CATALOG
    if not any(r["qId"] in _GATED_QIDS for r in c["bonuses"])
}
# Linear tie-breakers for stage 2: ungated pure-discriminator questions (zero
# weight for every career) whose primary (+3) signals all belong to the ungated
# careers — i.e., the questions that exist to make those careers reachable from
# every branch. (q11-q13 host +3 rules for gated careers like backend/devops, and
# q5 is weighted, so none of them qualify — currently this selects exactly q18.)
LINEAR_DISCRIMINATORS = [
    q["id"] for q in _QUESTION_BANK
    if "show_if" not in q
    and not any(c["weights"].get(q["id"], 0) for c in _CAREER_CATALOG)
    and (primary := [
        c["id"] for c in _CAREER_CATALOG for r in c["bonuses"]
        if r["qId"] == q["id"] and r["bonus"] >= 3
    ])
    and all(cid in _UNGATED_CAREER_IDS for cid in primary)
]


def _bonus_key(careers: list[dict], qid: str) -> dict[int, list[str]]:
    """option value -> career ids carrying a bonus on (qid, option)."""
    key: dict[int, list[str]] = {}
    for c in careers:
        for r in c["bonuses"]:
            if r["qId"] == qid:
                key.setdefault(r["answerValue"], []).append(c["id"])
    return key


def candidate_ids(answers: dict, careers: list[dict]) -> list[str] | None:
    """Deterministic stage 1. None => q2 unanswered, fall back to the 16-way vote."""
    family_q = GATED_BY_Q2.get(answers.get("q2"))
    if family_q is None:
        return None
    family = [c["id"] for c in careers if any(r["qId"] == family_q for r in c["bonuses"])]
    gated = set(GATED_BY_Q2.values())
    always = [
        c["id"] for c in careers
        if c["id"] not in family and not any(r["qId"] in gated for r in c["bonuses"])
        and any(r["qId"] in LINEAR_DISCRIMINATORS for r in c["bonuses"])
    ]
    return family + always


def _render_tiebreakers(answers: dict, questions: list[dict], shortlist: list[dict]) -> str:
    by_id = {q["id"]: q for q in questions}
    blocks = []
    for qid in [GATED_BY_Q2[answers["q2"]], *LINEAR_DISCRIMINATORS]:
        q = by_id[qid]
        key = _bonus_key(shortlist, qid)
        legend = "\n".join(
            f"    option \"{q['options'][av]}\" -> points to {', '.join(key[av])}"
            for av in sorted(key)
        )
        val = answers.get(qid)
        if qid not in answers or val is None:
            chosen = "(they skipped this question — no signal here)"
        else:
            chosen = f"THEY CHOSE: \"{q['options'][int(val)]}\""
        blocks.append(f"- Question: {q['text']}\n  What each option indicates:\n{legend}\n  {chosen}")
    return "\n".join(blocks)


def build_shortlist_prompt(persona_desc: str, answers: dict, questions: list[dict],
                           shortlist: list[dict]) -> str:
    ids = json.dumps([c["id"] for c in shortlist])
    profile_text = render_profile(answers, questions)
    tiebreakers = _render_tiebreakers(answers, questions, shortlist)
    return f"""You are {persona_desc}.
A first screening pass already narrowed one beginner's best-fit tech careers down to this
shortlist based on their broad interests. Your job is the FINAL call between these closely
related careers. They look similar from general answers, so general impressions will NOT
separate them — the questionnaire has dedicated tie-breaker questions for exactly this
shortlist, and each tie-breaker option was written to indicate specific careers.

The shortlist (choose only from these):
{render_careers(shortlist)}

The tie-breaker questions, what each option indicates, and what this person chose:
{tiebreakers}

Decision rule, in order:
1) The person's chosen tie-breaker option is their own description of the work they want.
   Recommend the career it points to. General answers about beauty, polish, visuals, or
   comfort with code are NOT a contradiction — every career on this shortlist shares them,
   which is exactly why the tie-breaker question exists. Override a tie-breaker choice only
   if a DIFFERENT tie-breaker points elsewhere or it was skipped.
2) If the tie-breakers point at different careers, or one was skipped, use the full
   profile below to decide between the indicated careers.
3) Only if all tie-breakers were skipped, judge from the full profile alone.

Their full questionnaire answers, for context:
{profile_text}

Return STRICT JSON ONLY with this exact schema:
{{
  "top1": "career id",
  "top2": "career id or null",
  "confidence": 0.0,
  "explanation": "string"
}}

Rules:
1) "top1" is required and must be one of: {ids}
2) Always provide "top2" — your second-best fit from the same list, different from top1.
3) "confidence" is your confidence in top1, a number in [0, 1].
4) "explanation" must cite the tie-breaker answer(s) (or explain why you overrode them).
""".strip()


def build_vote_call(persona_desc: str, profile: dict, questions: list[dict],
                    careers: list[dict]) -> tuple[str, set[str]]:
    """Prompt + valid career ids for one panel vote: shortlist stage-2 when q2 was
    answered, the original 16-way prompt otherwise."""
    answers = profile["answers"]
    cands = candidate_ids(answers, careers)
    if cands is None:
        return build_label_prompt(persona_desc, render_profile(answers, questions), careers), {c["id"] for c in careers}
    shortlist = [c for c in careers if c["id"] in cands]
    return build_shortlist_prompt(persona_desc, answers, questions, shortlist), set(cands)


def build_archetype_prompt(persona_desc: str, career: dict, questions: list[dict]) -> str:
    q_lines = []
    for q in questions:
        opts = " / ".join(f"{i}=\"{opt}\"" for i, opt in enumerate(q["options"]))
        q_lines.append(f"- {q['id']}: {q['text']}  Options: {opts}")
    example = "{" + ", ".join(f'"{q["id"]}": 0' for q in questions) + "}"
    return f"""You are {persona_desc}.
Answer this career-orientation questionnaire as the IDEAL candidate for the career
"{career['title']}" ({career['id']}) would answer it. Pick the option index (0-3) that
the archetypal {career['title']} would choose for each question.

Questions:
{chr(10).join(q_lines)}

Return STRICT JSON ONLY:
{example}

Every value must be an integer 0-3.
""".strip()


# ---------------------------------------------------------------- ollama
def _repair_truncated_json(raw: str) -> str:
    s = raw.rstrip()
    in_string = False
    escaped = False
    for ch in s:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        s += '"'
    opens: list[str] = []
    in_string = False
    escaped = False
    for ch in s:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            opens.append(ch)
        elif ch == "}" and opens and opens[-1] == "{":
            opens.pop()
        elif ch == "]" and opens and opens[-1] == "[":
            opens.pop()
    for opener in reversed(opens):
        s += "]" if opener == "[" else "}"
    return s


def call_ollama(prompt: str, temperature: float = TEMPERATURE) -> dict:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature, "num_predict": NUM_PREDICT},
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_S)
    response.raise_for_status()
    raw = response.json().get("response", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_repair_truncated_json(raw))


# ---------------------------------------------------------------- labeling
_write_lock = threading.Lock()


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def validate_vote(raw: dict, career_ids: set[str]) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("not a JSON object")
    top1 = raw.get("top1")
    if top1 not in career_ids:
        raise ValueError(f"invalid top1: {top1!r}")
    top2 = raw.get("top2")
    if top2 not in career_ids or top2 == top1:
        top2 = None
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "top1": top1,
        "top2": top2,
        "confidence": confidence,
        "explanation": str(raw.get("explanation", "")).strip()[:400],
    }


def label_profiles(profiles: list[dict], questions: list[dict], careers: list[dict]) -> None:
    career_ids = {c["id"] for c in careers}
    # Resume only within the current PROMPT_VERSION: a prompt bump changes what the
    # panel was asked (and profile ids like syn_0042 are reused across generations),
    # so older log entries are provenance, never completed work.
    done = {
        (v["profile_id"], v["persona_id"])
        for v in read_jsonl(VOTES_JSONL)
        if not v.get("error") and v.get("prompt_version") == PROMPT_VERSION
    }
    jobs = [
        (profile, persona_id, persona_desc, persona_temp)
        for profile in profiles
        for persona_id, persona_desc, persona_temp in PERSONAS
        if (profile["profile_id"], persona_id) not in done
    ]
    if not jobs:
        print("All panel votes already present; skipping labeling.")
        return
    print(f"Panel labeling: {len(jobs)} votes to collect ({len(done)} already logged)")

    def _one(job) -> dict:
        profile, persona_id, persona_desc, persona_temp = job
        prompt, valid_ids = build_vote_call(persona_desc, profile, questions, careers)
        error = ""
        vote = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                vote = validate_vote(call_ollama(prompt, persona_temp), valid_ids)
                break
            except Exception as exc:  # noqa: BLE001 - log and retry
                error = f"attempt_{attempt}: {exc}"
        record = {
            "profile_id": profile["profile_id"],
            "profile_source": profile["profile_source"],
            "answers": profile["answers"],
            "persona_id": persona_id,
            "model_name": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "temperature": persona_temp,
            "label_source": LABEL_SOURCE,
            "timestamp_utc": now_utc(),
        }
        if vote is not None:
            record.update(vote)
            record["error"] = ""
        else:
            record.update({"top1": None, "top2": None, "confidence": 0.0, "explanation": "", "error": error})
        append_jsonl(VOTES_JSONL, record)
        return record

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(_one, job) for job in jobs]
        for future in tqdm(as_completed(futures), total=len(jobs), desc="Panel votes"):
            future.result()


def collect_archetypes(questions: list[dict], careers: list[dict]) -> None:
    # Same PROMPT_VERSION scoping as label_profiles: pre-bump archetypes may not even
    # cover the current question bank (v1.1.0 rows stop at q10).
    done = {
        (a["career_id"], a["persona_id"])
        for a in read_jsonl(ARCHETYPES_JSONL)
        if not a.get("error") and a.get("prompt_version") == PROMPT_VERSION
    }
    jobs = [
        (career, persona_id, persona_desc, persona_temp)
        for career in careers
        for persona_id, persona_desc, persona_temp in PERSONAS
        if (career["id"], persona_id) not in done
    ]
    if not jobs:
        print("All archetypes already present; skipping.")
        return
    print(f"Archetype collection: {len(jobs)} to collect")

    def _one(job) -> None:
        career, persona_id, persona_desc, persona_temp = job
        prompt = build_archetype_prompt(persona_desc, career, questions)
        error = ""
        answers = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = call_ollama(prompt, persona_temp)
                candidate = {}
                for qid in QUESTION_IDS:
                    val = int(raw[qid])
                    if not 0 <= val <= 3:
                        raise ValueError(f"{qid} out of range: {val}")
                    candidate[qid] = val
                answers = candidate
                break
            except Exception as exc:  # noqa: BLE001
                error = f"attempt_{attempt}: {exc}"
        append_jsonl(ARCHETYPES_JSONL, {
            "career_id": career["id"],
            "persona_id": persona_id,
            "answers": answers,
            "model_name": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "temperature": persona_temp,
            "label_source": LABEL_SOURCE,
            "timestamp_utc": now_utc(),
            "error": error if answers is None else "",
        })

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(_one, job) for job in jobs]
        for future in tqdm(as_completed(futures), total=len(jobs), desc="Archetypes"):
            future.result()


# ---------------------------------------------------------------- agreement stats
def fleiss_kappa(votes_by_profile: list[list[str]], categories: list[str]) -> float:
    """Fleiss' kappa; requires the same number of raters per subject."""
    counts = np.array([
        [votes.count(cat) for cat in categories]
        for votes in votes_by_profile
    ], dtype=float)
    n_raters = counts.sum(axis=1)
    if len(set(n_raters.tolist())) != 1:
        raise ValueError("unequal rater counts")
    n = n_raters[0]
    if n < 2:
        return float("nan")
    p_i = ((counts * counts).sum(axis=1) - n) / (n * (n - 1))
    p_bar = p_i.mean()
    p_j = counts.sum(axis=0) / counts.sum()
    p_e = (p_j ** 2).sum()
    if abs(1 - p_e) < 1e-12:
        return float("nan")
    return float((p_bar - p_e) / (1 - p_e))


def cohen_kappa(a: list[str], b: list[str], categories: list[str]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum(
        (a.count(cat) / n) * (b.count(cat) / n)
        for cat in categories
    )
    if abs(1 - pe) < 1e-12:
        return float("nan")
    return (po - pe) / (1 - pe)


def heuristic_fit_top1(answers: dict, careers: list[dict]) -> str:
    """Current formula's questionnaire_fit component only (offline; no RAG signals)."""
    best_id, best_score = None, float("-inf")
    for career in sorted(careers, key=lambda c: c["id"]):
        score = 0
        for qid, weight in career["weights"].items():
            val = answers.get(qid)
            if val is not None:
                score += val * weight
        for rule in career.get("bonuses", []):
            if answers.get(rule["qId"]) == rule["answerValue"]:
                score += rule["bonus"] * 3
        if score > best_score:
            best_id, best_score = career["id"], score
    return best_id


# ---------------------------------------------------------------- aggregation
def aggregate(careers: list[dict]) -> None:
    career_ids = [c["id"] for c in careers]
    # Aggregate only the current PROMPT_VERSION's log entries — mixing generations
    # would reuse labels collected under a different prompt/catalog/question bank.
    log = [v for v in read_jsonl(VOTES_JSONL) if v.get("prompt_version") == PROMPT_VERSION]
    votes = [v for v in log if not v.get("error") and v.get("top1")]
    failures = [v for v in log if v.get("error")]
    if not votes:
        raise SystemExit(
            f"No successful {PROMPT_VERSION} votes logged; nothing to aggregate "
            "(older-version votes are ignored — run labeling first)."
        )

    by_profile: dict[str, list[dict]] = {}
    for v in votes:
        by_profile.setdefault(v["profile_id"], []).append(v)

    complete = {pid: vs for pid, vs in by_profile.items() if len({v["persona_id"] for v in vs}) == len(PERSONAS)}
    dropped = set(by_profile) - set(complete)

    silver_rows, ambiguous_rows = [], []
    for pid, vs in sorted(complete.items()):
        vs = sorted(vs, key=lambda v: v["persona_id"])
        top1s = [v["top1"] for v in vs]
        counts = pd.Series(top1s).value_counts()
        consensus = counts.index[0] if counts.iloc[0] >= CONSENSUS_MIN_VOTES else None
        top2_votes = [v["top2"] for v in vs if v["top2"]]
        panel_top2 = pd.Series(top2_votes).value_counts().index[0] if top2_votes else None
        if panel_top2 == consensus:
            panel_top2 = next((t for t in top2_votes if t != consensus), None)
        row = {
            "profile_id": pid,
            "profile_source": vs[0]["profile_source"],
            "answers_json": json.dumps(vs[0]["answers"], ensure_ascii=True),
            "label_top1": consensus,
            "label_top2": panel_top2,
            "consensus_votes": int(counts.iloc[0]),
            "n_raters": len(vs),
            "mean_confidence": float(np.mean([v["confidence"] for v in vs])),
            "votes_json": json.dumps(
                [{k: v[k] for k in ("persona_id", "temperature", "top1", "top2", "confidence", "explanation")} for v in vs],
                ensure_ascii=True,
            ),
            "heuristic_fit_top1": heuristic_fit_top1(vs[0]["answers"], careers),
            "model_name": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "temperature": "per-persona (see votes_json)",
            "label_source": LABEL_SOURCE,
            "created_at": now_utc(),
        }
        (silver_rows if consensus else ambiguous_rows).append(row)

    silver = pd.DataFrame(silver_rows)
    ambiguous = pd.DataFrame(ambiguous_rows)
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(SILVER_PARQUET, index=False)
    ambiguous.to_parquet(AMBIGUOUS_PARQUET, index=False)

    arch_records = [
        a for a in read_jsonl(ARCHETYPES_JSONL)
        if not a.get("error") and a.get("answers") and a.get("prompt_version") == PROMPT_VERSION
    ]
    archetypes = pd.DataFrame([
        {
            "career_id": a["career_id"],
            "persona_id": a["persona_id"],
            **{qid: a["answers"][qid] for qid in QUESTION_IDS},
            "model_name": a["model_name"],
            "prompt_version": a["prompt_version"],
            "temperature": a["temperature"],
            "label_source": a["label_source"],
            "created_at": a["timestamp_utc"],
        }
        for a in arch_records
    ])
    archetypes.to_parquet(ARCHETYPES_PARQUET, index=False)

    # --- agreement stats (over complete profiles only)
    persona_ids = [p for p, _, _ in PERSONAS]
    votes_matrix = {pid: {v["persona_id"]: v["top1"] for v in vs} for pid, vs in complete.items()}
    ordered_pids = sorted(votes_matrix)
    by_persona = {p: [votes_matrix[pid][p] for pid in ordered_pids] for p in persona_ids}
    fleiss = fleiss_kappa([[votes_matrix[pid][p] for p in persona_ids] for pid in ordered_pids], career_ids)
    pairwise = {
        f"{a} vs {b}": cohen_kappa(by_persona[a], by_persona[b], career_ids)
        for a, b in combinations(persona_ids, 2)
    }

    all_labeled = pd.concat([silver, ambiguous]) if not ambiguous.empty else silver
    formula_agree = float((silver["label_top1"] == silver["heuristic_fit_top1"]).mean()) if not silver.empty else float("nan")

    real_pids = [pid for pid in ordered_pids if votes_matrix[pid] and pid.startswith("real_")]

    def dist_table(series: pd.Series) -> str:
        counts = series.value_counts()
        lines = ["| career | count | share |", "|---|---|---|"]
        for cid in career_ids:
            c = int(counts.get(cid, 0))
            lines.append(f"| {cid} | {c} | {c / max(len(series), 1):.1%} |")
        return "\n".join(lines)

    unanimous = int((silver["consensus_votes"] == len(PERSONAS)).sum()) if not silver.empty else 0
    sample = silver.sample(min(20, len(silver)), random_state=RANDOM_SEED) if not silver.empty else silver

    report = f"""# Synthetic Agreement Report — LLM Panel Silver Labels

> **These are SILVER labels produced by a local LLM panel, not human expert ground
> truth.** All agreement numbers below measure consistency between LLM personas
> sharing one base model ({MODEL_NAME}); they are NOT a human inter-expert noise
> ceiling and must never be presented as expert validation.

Generated: {now_utc()}  |  model: `{MODEL_NAME}`  |  prompt: `{PROMPT_VERSION}`  |  temperatures: {", ".join(f"{p}={t}" for p, _, t in PERSONAS)}

## Pool

- Profiles labeled (complete 3-persona panels): **{len(complete)}** ({len(real_pids)} real from public.submissions, {len(complete) - len(real_pids)} synthetic-generated)
- Incomplete panels dropped: {len(dropped)}
- Failed votes (after retries): {len(failures)}
- **NOTE:** public.submissions held only 7 real submissions at labeling time, so the
  pool is dominated by generated synthetic profiles (seeded/mixed/random over the
  answer space, adaptive branching respected). `profile_source` distinguishes them.

## Consensus filtering (>= {CONSENSUS_MIN_VOTES}/{len(PERSONAS)} personas agree on top-1)

- High-consensus -> `silver_labels.parquet`: **{len(silver)}** (unanimous: {unanimous})
- Low-agreement -> `ambiguous_labels.parquet`: **{len(ambiguous)}**

## Synthetic agreement (NOT human agreement)

- Fleiss' kappa ({len(PERSONAS)} personas, {len(career_ids)} careers): **{fleiss:.3f}**
{chr(10).join(f"- Cohen's kappa {k}: {v:.3f}" for k, v in pairwise.items())}

Interpretation caution: personas share one base model, so high kappa here means
self-consistency, not correctness. Near-perfect kappa would be a red flag for
persona non-independence rather than a quality guarantee.

## Label distribution (silver consensus top-1)

{dist_table(silver["label_top1"]) if not silver.empty else "(empty)"}

## Per-persona top-1 distribution (all complete panels)

{chr(10).join(f"### {p}{chr(10)}{dist_table(pd.Series(by_persona[p]))}" for p in persona_ids)}

## Formula-vs-panel agreement (circularity check)

The current hand-authored questionnaire_fit heuristic's top-1 agrees with the panel
consensus on **{formula_agree:.1%}** of silver profiles. High agreement means the
learned-vs-formula comparison in Phase 2 is partly circular (the panel may reason
like the hand weights); note this when reading Gate 1 results.

## Confidence

- Mean panel confidence (silver): {silver["mean_confidence"].mean():.2f}
- Mean panel confidence (ambiguous): {(ambiguous["mean_confidence"].mean() if not ambiguous.empty else float("nan")):.2f}

## Gate 0 checklist

- [ ] Synthetic agreement acceptable (kappa neither near 0 nor suspiciously ~1.0) — see numbers above
- [ ] Label distribution plausible (no career ~0%, none dominating) — see table above
- [ ] Manual sanity check of the sample below passed

## Manual sanity-check sample ({len(sample)} silver rows)

{chr(10).join(f"- **{r.profile_id}** ({r.profile_source}) -> {r.label_top1} (votes {r.consensus_votes}/{r.n_raters}, conf {r.mean_confidence:.2f}); answers `{r.answers_json}`; first explanation: {json.loads(r.votes_json)[0]['explanation']!r}" for r in sample.itertuples())}
"""
    REPORT_MD.write_text(report, encoding="utf-8")

    print(f"silver={len(silver)} ambiguous={len(ambiguous)} archetypes={len(archetypes)}")
    print(f"fleiss_kappa={fleiss:.3f} formula_agreement={formula_agree:.1%}")
    print(f"Wrote {SILVER_PARQUET}, {AMBIGUOUS_PARQUET}, {ARCHETYPES_PARQUET}, {REPORT_MD}")


def ensure_label_coverage(questions: list[dict], careers: list[dict], max_rounds: int) -> None:
    """Bounded closed-loop top-up: while any career has fewer than
    MIN_LABELS_PER_CAREER silver labels, add pinned-cue seeded profiles for the
    starved careers, label them, and re-aggregate. Label counts depend on the
    panel's votes, so no static generation mix can guarantee them — this loop can.
    Exits nonzero if the round cap is hit with coverage still short (fail loud,
    same contract as dataset_guards)."""

    def shortfall() -> dict[str, int]:
        counts = pd.read_parquet(SILVER_PARQUET)["label_top1"].value_counts()
        return {cid: int(counts.get(cid, 0)) for cid in CAREER_IDS
                if counts.get(cid, 0) < MIN_LABELS_PER_CAREER}

    def topup_profile(cid: str, round_no: int, i: int) -> dict:
        # Randomness is derived from the profile id itself, never from a shared
        # sequential RNG: label_profiles resumes by (profile_id, persona_id), so a
        # given id must always map to the same answers — even when an interrupted
        # run restarts with a different shortfall career set for the same round.
        pid = f"syn_c{round_no:02d}{i:02d}_{cid}"
        rng = random.Random(f"{RANDOM_SEED}:{pid}")
        return {
            "profile_id": pid,
            "profile_source": "synthetic",
            "answers": perturb_seed(CAREER_SEEDS[cid], rng, SEED_NOISE, pinned_qids(cid)),
        }

    for round_no in range(1, max_rounds + 1):
        short = shortfall()
        if not short:
            print(f"Label coverage ok: every career has >= {MIN_LABELS_PER_CAREER} silver labels.")
            return
        profiles = [
            topup_profile(cid, round_no, i)
            for cid in short
            for i in range(TOPUP_BATCH)
        ]
        print(f"Coverage round {round_no}/{max_rounds}: short={short}; labeling {len(profiles)} top-ups")
        label_profiles(profiles, questions, careers)
        aggregate(careers)

    short = shortfall()
    if short:
        raise SystemExit(
            f"Coverage top-up exhausted after {max_rounds} rounds; still short: {short}. "
            "The panel is not producing these labels at a usable rate — see the "
            "protocol-ceiling discussion on PR #15 before rerunning."
        )
    print(f"Label coverage ok: every career has >= {MIN_LABELS_PER_CAREER} silver labels.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="label only the first N profiles (smoke test)")
    parser.add_argument("--n-synthetic", type=int, default=N_SYNTHETIC_PROFILES)
    parser.add_argument("--aggregate-only", action="store_true")
    parser.add_argument("--skip-archetypes", action="store_true")
    parser.add_argument("--max-topup-rounds", type=int, default=MAX_TOPUP_ROUNDS,
                        help="coverage top-up round cap (0 disables the coverage loop)")
    args = parser.parse_args()

    questions, careers = load_catalog()
    if not args.aggregate_only:
        profiles = load_profiles(args.n_synthetic)
        if args.limit:
            profiles = profiles[: args.limit]
        label_profiles(profiles, questions, careers)
        if not args.skip_archetypes:
            collect_archetypes(questions, careers)
    aggregate(careers)
    # Coverage loop only on full runs: smoke tests (--limit) and aggregate-only
    # recomputations must not trigger new labeling.
    if not args.aggregate_only and not args.limit and args.max_topup_rounds > 0:
        ensure_label_coverage(questions, careers, args.max_topup_rounds)


if __name__ == "__main__":
    main()
