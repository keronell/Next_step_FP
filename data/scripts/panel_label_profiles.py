"""Phase 0 of the matching-module rework: synthetic silver labels from a local LLM panel.

Labels questionnaire profiles (real ones exported from public.submissions plus
generated synthetic ones) with multiple synthetic expert personas via local Ollama.
The labels are SILVER labels — LLM-generated, not expert ground truth.

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

# ---------------------------------------------------------------- configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b-instruct"
TEMPERATURE = 0.2  # fallback; personas carry their own (see PERSONAS)
NUM_PREDICT = 300
# v1.2.0: career count/coaching derived from the catalog (16 careers), no hardcoded six.
# v1.3.0: 18-question bank (q14-q18 discriminators) — profiles/archetypes rendered under
# the old bank must not resume or aggregate into this generation (resume and aggregate
# are scoped to PROMPT_VERSION, so any bank/catalog change needs a bump like this one).
PROMPT_VERSION = "panel-v1.3.0"
LABEL_SOURCE = "synthetic_llm"
MAX_RETRIES = 2
WORKERS = 4
TIMEOUT_S = 120

N_SYNTHETIC_PROFILES = 200
RANDOM_SEED = 42
CONSENSUS_MIN_VOTES = 2  # of the 3 personas

QUESTIONS_JSON = Path("backend/app/data/questions.json")
CAREERS_JSON = Path("backend/app/data/careers.json")

# Single source of truth for the question set — derived from the bank, never
# hardcoded, so new questions (e.g. q11+) flow into synthetic profiles and
# archetypes automatically. Mirrors feature_builder.QUESTION_IDS on the serving side.
_QUESTION_BANK = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
QUESTION_IDS = [q["id"] for q in _QUESTION_BANK]
# Career universe, same principle: derived from the catalog in catalog order.
CAREER_IDS = [c["id"] for c in json.loads(CAREERS_JSON.read_text(encoding="utf-8"))]
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


def generate_synthetic_profiles(n: int, rng: random.Random) -> list[dict]:
    career_ids = list(CAREER_SEEDS)
    profiles = []

    def perturb(seed_answers: dict, noise: float) -> dict:
        answers = {}
        for qid in QUESTION_IDS:
            val = seed_answers.get(qid, rng.randint(0, 3))
            if rng.random() < noise:
                val = rng.randint(0, 3)
            if rng.random() < 0.05:  # occasional skip, like real users
                val = None
            answers[qid] = val
        return apply_branching(answers)

    n_seeded = int(n * 0.3)
    n_mixed = int(n * 0.3)
    n_random = n - n_seeded - n_mixed

    for i in range(n_seeded):
        cid = career_ids[i % len(career_ids)]
        profiles.append(perturb(CAREER_SEEDS[cid], noise=0.35))
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
        prompt = build_label_prompt(persona_desc, render_profile(profile["answers"], questions), careers)
        error = ""
        vote = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                vote = validate_vote(call_ollama(prompt, persona_temp), career_ids)
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="label only the first N profiles (smoke test)")
    parser.add_argument("--n-synthetic", type=int, default=N_SYNTHETIC_PROFILES)
    parser.add_argument("--aggregate-only", action="store_true")
    parser.add_argument("--skip-archetypes", action="store_true")
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


if __name__ == "__main__":
    main()
