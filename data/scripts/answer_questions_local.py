"""Synthetic expert-answer generation for the question bank (field-prediction bootstrap).

Each question-bank row is answered "in character" by a synthetic persona representing
one of the 16 canonical fields, producing a soft multi-field distribution used as
training-target bootstrap for the (not-yet-built) neural field matcher described in
data/docs/NEURAL_MATCHER_DESIGN.md. These are SILVER labels -- LLM-generated, not
expert ground truth (same caveat as docs/matching-rework-plan.md Phase 0).

Architecture mirrors data/scripts/panel_label_profiles.py (the shipped Phase-0 panel
behind the career matcher), applied to a different unit of labeling (question-bank
rows instead of questionnaire profiles):

  - Each field is judged by PERSONAS_PER_FIELD independent personas at DISTINCT
    temperatures (PERSONA_TEMPERATURES) instead of one fixed temperature for
    everyone. The career panel's first iteration (panel-v1.0.1) had all personas on
    one temperature and got a suspiciously high Fleiss kappa (0.930) because the
    "independent" raters were clones of the same base model; per-persona temperature
    (v1.1.0) was the fix, applied here the same way.
  - The prompt explicitly says every field is equally valid and warns against
    defaulting to coding-heavy fields -- the career panel needed the identical fix
    after v1.0.1 defaulted to developer roles (ux-designer 0%, product-manager 2.9%).
  - The target field is never force-injected into predicted_fields. Earlier versions
    of this script added target_field to predicted_fields whenever the model didn't
    include it, which made "does the panel confirm this field?" a meaningless 100%
    by construction (see the pre-rework validation report: every row "passed" target
    consistency because the code guaranteed it, not because the model agreed).
    `target_confirmed` in the agreement report is now computed straight from what the
    model actually returned.
  - Where the generation plan gives a field's personas a shared question subset
    (SHARED_QUESTION_RATIO), agreement across those personas is reported the same way
    the career panel reports Fleiss/Cohen kappa: a real, if partial, synthetic
    inter-rater signal -- not human validation.

Outputs:
    data/answers/question_bank_answered_local.csv   one row per (question, persona)
    data/answers/annotation_failures.jsonl           rows that failed after retries
    data/reports/question_bank_agreement_report.md   confirmation rates + kappa

Usage:
    python data/scripts/answer_questions_local.py                  # full run
    python data/scripts/answer_questions_local.py --limit 50       # smoke test
    python data/scripts/answer_questions_local.py --aggregate-only # recompute report only
"""
import argparse
import csv
import json
import random
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm


INPUT_CSV = Path("data/questions/question_bank.csv")
OUTPUT_CSV = Path("data/answers/question_bank_answered_local.csv")
FAILURES_JSONL = Path("data/answers/annotation_failures.jsonl")
REPORT_MD = Path("data/reports/question_bank_agreement_report.md")
MODEL_FAST = "qwen2.5:7b-instruct"
MODEL_STRONG = "qwen3:14b"
USE_STRONG_FALLBACK = False
OLLAMA_URL = "http://localhost:11434/api/generate"
PROMPT_VERSION = "v4.1.0"  # v4.0.0: panel architecture + honest confirmation; v4.1.0: two-job
                           # prompt (discriminative Likert + question classification separated)
MAX_RETRIES = 2
NUM_PREDICT_FAST = 512   # was 450; 6.9% of the legacy run had <5 nonzero field_scores,
                         # partly silent JSON truncation that normalize_scores then zeros out
NUM_PREDICT_STRONG = 640
MIN_SAMPLES_PER_FIELD = 5
GENERATION_MODE = "partitioned_shared_20"  # "balanced", "exhaustive", or "partitioned_shared_20"
SHARED_QUESTION_RATIO = 0.05   # fraction of questions every persona in a field answers in common
PERSONAS_PER_FIELD = 3         # independent personas per field, each at its own temperature below
                               # (mirrors panel_label_profiles.py's 3-persona panel; was a single
                               # persona pair at one fixed temperature=0.1, which under-diversified
                               # the "independent" raters)
PERSONA_TEMPERATURES = [0.2, 0.6, 0.9]  # per-persona-slot temperature; cycled if PERSONAS_PER_FIELD > 3
MAX_UNIQUE_PER_PERSONA = 100   # cap unique questions per persona; None = no cap
OLLAMA_WORKERS = 4             # parallel Ollama requests; set OLLAMA_NUM_PARALLEL=N on Ollama side
RANDOM_SEED = 42
RESUME_FROM_EXISTING = True
CONSENSUS_MIN_VOTES = 2        # of PERSONAS_PER_FIELD, for shared-subset agreement reporting

CANONICAL_FIELDS = [
    "Frontend Development",
    "Backend Development",
    "Full Stack Development",
    "Mobile Development",
    "Data Analysis",
    "Data Science",
    "Machine Learning",
    "AI Engineering",
    "Cyber Security",
    "DevOps",
    "QA / Software Testing",
    "Game Development",
    "UI / UX Design",
    "Product Management",
    "Technical Writing",
    "Software Architecture",
]

EXPERT_MAP = {
    "qa": "Senior Quality Assurance Engineer",
    "quality assurance": "Senior Quality Assurance Engineer",
    "software testing": "Senior Software Test Engineer",
    "personality": "Industrial-Organizational Psychologist",
    "creativity": "Creativity and Design Thinking Coach",
    "data": "Senior Data Analyst",
    "analytics": "Senior Data Analyst",
    "design": "Senior Product Designer",
    "engineering": "Senior Software Engineer",
    "security": "Cybersecurity Specialist",
    "marketing": "Growth Marketing Strategist",
    "finance": "Financial Analyst",
    "hr": "Human Resources Specialist",
}

FIELD_PERSONAS = {
    "Frontend Development": [
        "Senior Frontend Engineer",
        "Frontend Architect",
        "React Performance Specialist",
        "Web Accessibility Engineer",
        "UI Platform Engineer",
    ],
    "Backend Development": [
        "Senior Backend Engineer",
        "Backend Systems Architect",
        "Distributed Systems Engineer",
        "API Platform Engineer",
        "Database Reliability Engineer",
    ],
    "Full Stack Development": [
        "Senior Full Stack Engineer",
        "Technical Lead (Full Stack)",
        "Product-Oriented Full Stack Developer",
        "Web Application Engineer",
        "Startup Full Stack Engineer",
    ],
    "Mobile Development": [
        "Senior Mobile Engineer",
        "Mobile App Architect",
        "Android Engineer",
        "iOS Engineer",
        "Cross-Platform Mobile Engineer",
    ],
    "Data Analysis": [
        "Senior Data Analyst",
        "Business Intelligence Analyst",
        "Product Analytics Specialist",
        "Operations Data Analyst",
        "Decision Intelligence Analyst",
    ],
    "Data Science": [
        "Data Scientist",
        "Senior Quantitative Analyst",
        "Experimentation Scientist",
        "Statistical Modeling Scientist",
        "Applied Data Scientist",
    ],
    "Machine Learning": [
        "Machine Learning Engineer",
        "ML Research Engineer",
        "Applied ML Engineer",
        "Model Optimization Engineer",
        "MLOps-Integrated ML Engineer",
    ],
    "AI Engineering": [
        "AI Engineer",
        "Applied AI Systems Engineer",
        "LLM Application Engineer",
        "AI Infrastructure Engineer",
        "Generative AI Engineer",
    ],
    "Cyber Security": [
        "Cyber Security Engineer",
        "Security Operations Specialist",
        "Application Security Engineer",
        "Cloud Security Engineer",
        "Threat Detection Analyst",
    ],
    "DevOps": [
        "DevOps Engineer",
        "Site Reliability Engineer",
        "Platform Engineer",
        "CI/CD Automation Engineer",
        "Infrastructure-as-Code Engineer",
    ],
    "QA / Software Testing": [
        "Senior QA Engineer",
        "Test Automation Engineer",
        "Quality Engineering Lead",
        "Performance Test Engineer",
        "Software Validation Specialist",
    ],
    "Game Development": [
        "Game Developer",
        "Gameplay Systems Engineer",
        "Game Engine Programmer",
        "Technical Game Designer",
        "Real-Time Graphics Engineer",
    ],
    "UI / UX Design": [
        "Senior Product Designer",
        "UX Researcher",
        "Interaction Designer",
        "Design Systems Specialist",
        "Usability Expert",
    ],
    "Product Management": [
        "Product Manager",
        "Technical Product Manager",
        "Growth Product Manager",
        "Platform Product Manager",
        "Data-Informed Product Strategist",
    ],
    "Technical Writing": [
        "Technical Writer",
        "Developer Documentation Specialist",
        "API Documentation Writer",
        "Knowledge Base Architect",
        "Technical Content Strategist",
    ],
    "Software Architecture": [
        "Software Architect",
        "Principal Engineer",
        "Enterprise Architect",
        "Distributed Systems Architect",
        "Scalability Architecture Specialist",
    ],
}

FIELD_KEYWORDS = {
    "Frontend Development": ["frontend", "ui", "web", "interface"],
    "Backend Development": ["backend", "api", "database", "server", "service"],
    "Full Stack Development": ["full stack", "frontend", "backend", "web app"],
    "Mobile Development": ["mobile", "android", "ios", "app"],
    "Data Analysis": ["data", "analytics", "dashboard", "insight", "analysis"],
    "Data Science": ["data science", "statistics", "model", "experimentation"],
    "Machine Learning": ["machine learning", "ml", "training", "inference", "model"],
    "AI Engineering": ["ai", "llm", "agent", "genai", "model deployment"],
    "Cyber Security": ["security", "cyber", "vulnerability", "threat", "authentication"],
    "DevOps": ["devops", "ci/cd", "deployment", "infra", "reliability", "sre"],
    "QA / Software Testing": ["qa", "testing", "test", "quality", "bug"],
    "Game Development": ["game", "gameplay", "unity", "unreal"],
    "UI / UX Design": ["ux", "ui", "design", "user research", "wireframe"],
    "Product Management": ["product", "roadmap", "prioritization", "stakeholder", "impact"],
    "Technical Writing": ["documentation", "writing", "explain", "guide", "docs"],
    "Software Architecture": ["architecture", "scalability", "system design", "distributed", "design"],
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def choose_expert(category: str, subcategory: str, tags: str) -> str:
    text = f"{category} {subcategory} {tags}".lower()
    for key, role in EXPERT_MAP.items():
        if key in text:
            return role
    return "Domain Subject Matter Expert"


def normalize_scores(raw_scores: dict) -> dict:
    scores = {}
    for field in CANONICAL_FIELDS:
        value = raw_scores.get(field, 0.0)
        try:
            scores[field] = float(value)
        except (TypeError, ValueError):
            scores[field] = 0.0
        if scores[field] < 0:
            scores[field] = 0.0

    total = sum(scores.values())
    if total <= 0:
        uniform = 1.0 / len(CANONICAL_FIELDS)
        return {field: uniform for field in CANONICAL_FIELDS}
    return {field: scores[field] / total for field in CANONICAL_FIELDS}


def build_prompt(expert_role: str, target_field: str, row: pd.Series) -> str:
    question = str(row.get("question", "")).strip()
    answer_type = str(row.get("answer_type", "")).strip()
    options = str(row.get("options", "")).strip()
    category = str(row.get("category", "")).strip()
    subcategory = str(row.get("subcategory", "")).strip()
    tags = str(row.get("tags", "")).strip()
    fields_json = json.dumps(CANONICAL_FIELDS, ensure_ascii=True)
    is_likert = answer_type.strip().lower() == "likert5"

    if is_likert:
        job1 = f"""JOB 1 -- Answer as the expert (`score_1_to_5`).
This is a Likert5 question, so `score_1_to_5` MUST be an integer 1-5 -- NEVER null.
Treat the question as: "How well does this statement describe a typical
{target_field} professional?" Use the FULL 1-5 scale and discriminate honestly:
  5 = strongly describes someone in {target_field}
  4 = mostly describes them
  3 = neutral / only sometimes true
  2 = mostly does NOT describe them
  1 = strongly does NOT describe them
Do NOT default to 4. If the statement is off-theme for a {target_field} professional,
that is a 1 or 2 -- score it low, do NOT return null. "Does not apply to my field"
means 1, not null. Null is never a valid answer for this Likert5 question."""
    else:
        job1 = """JOB 1 -- Answer as the expert (`final_answer`).
This is NOT a Likert5 question, so set `score_1_to_5` to null and put your selection
(as the expert) in `final_answer`."""

    return f"""
You are a {expert_role}.
You are generating synthetic annotation data for a career-orientation questionnaire.
Stay in character as that expert. You have TWO separate jobs for this one question.

{job1}

JOB 2 -- Classify the QUESTION itself (`predicted_fields` + `field_scores`).
Independently of your persona, judge which of the 16 fields this question is actually
diagnostic of. This is a property of the question, not of you, so include
`{target_field}` only if the question genuinely relates to it -- never automatically
because it is your field. Do not let generic technical phrasing pull you toward
coding-heavy fields (Backend Development, Full Stack Development, Software
Architecture) by default; a question about people, process, communication, or visual
design belongs to the field it actually describes (e.g. Product Management,
UI / UX Design, Technical Writing).

Return STRICT JSON ONLY with this exact schema:
{{
  "expert_role": "string",
  "final_answer": "string",
  "reasoning": "string",
  "score_1_to_5": 1,
  "predicted_fields": ["string", "string", "string"],
  "field_scores": {{"Frontend Development": 0.01}},
  "confidence": 0.0
}}

Rules:
1) Keep `predicted_fields` length between 3 and 5, ranked most-relevant first.
2) `predicted_fields` values must come only from this list: {fields_json}
3) `field_scores` must include all 16 fields from the same list; give clearly
   irrelevant fields a low score, not zero, and let a few relevant fields stand out.
4) `field_scores` values must be numeric in [0, 1].
5) If `answer_type` is Likert5, set `score_1_to_5` as integer 1..5 per JOB 1; otherwise
   set null.
6) Keep `reasoning` to 1 short sentence naming the field(s) the question points to.
7) `confidence` in [0,1] is your confidence in the JOB 2 classification.

Context:
- Category: {category}
- Subcategory: {subcategory}
- Tags: {tags}
- Answer type: {answer_type}
- Options: {options}

Question:
{question}
""".strip()


def _repair_truncated_json(raw: str) -> str:
    """Close open brackets/braces in a truncated JSON string."""
    s = raw.rstrip()

    # Determine if we are inside an unterminated string literal.
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

    # Walk again to track open containers.
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


def call_ollama(prompt: str, model: str, num_predict: int, temperature: float, timeout_s: int = 180) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout_s)
    response.raise_for_status()
    raw = response.json().get("response", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_repair_truncated_json(raw))


def validate_and_shape(result: dict, fallback_expert: str, answer_type: str, target_field: str) -> dict:
    if not isinstance(result, dict):
        raise ValueError("Model output is not a JSON object.")

    field_scores = result.get("field_scores", {})
    if not isinstance(field_scores, dict):
        raise ValueError("field_scores must be an object.")
    normalized_scores = normalize_scores(field_scores)

    predicted_fields = result.get("predicted_fields", [])
    if not isinstance(predicted_fields, list):
        raise ValueError("predicted_fields must be a list.")
    cleaned_predicted = [f for f in predicted_fields if isinstance(f, str) and f in CANONICAL_FIELDS]
    cleaned_predicted = list(dict.fromkeys(cleaned_predicted))

    # Diagnostic only -- never force target_field into the prediction. Earlier
    # versions injected it here whenever the model omitted it, which made "does the
    # panel confirm this field?" unmeasurable (always 100% by construction). Honest
    # confirmation is what write_agreement_report() reports on.
    target_confirmed = target_field in cleaned_predicted

    if len(cleaned_predicted) < 3:
        top_fields = sorted(
            normalized_scores,
            key=lambda k: normalized_scores[k],
            reverse=True,
        )
        cleaned_predicted = list(dict.fromkeys(cleaned_predicted + top_fields))[:3]
    elif len(cleaned_predicted) > 5:
        cleaned_predicted = cleaned_predicted[:5]

    confidence = result.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    score = result.get("score_1_to_5", None)
    if str(answer_type).strip().lower() == "likert5":
        try:
            score = int(score)
            if score < 1 or score > 5:
                score = None
        except (TypeError, ValueError):
            score = None
    else:
        score = None

    return {
        "expert_role": str(result.get("expert_role", fallback_expert)),
        "model_answer": str(result.get("final_answer", "")).strip(),
        "model_reasoning": str(result.get("reasoning", "")).strip(),
        "model_score_1_to_5": score,
        "predicted_fields": json.dumps(cleaned_predicted, ensure_ascii=True),
        "field_scores_json": json.dumps(normalized_scores, ensure_ascii=True),
        "confidence": confidence,
        "target_confirmed": target_confirmed,
    }


_failure_lock = threading.Lock()


def append_failure(record: dict) -> None:
    FAILURES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    serializable_record = {
        k: (v.item() if hasattr(v, "item") else v)
        for k, v in record.items()
    }
    with _failure_lock:
        with FAILURES_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(serializable_record, ensure_ascii=True, default=str) + "\n")


# Fixed column order for the incrementally-written output CSV. One completed row is
# appended per (question x persona) as soon as it finishes -- so an interrupted run
# (machine sleep, kill, crash) keeps every row produced so far and a rerun resumes
# from the last saved row instead of losing hours of work. (The pre-checkpoint version
# buffered all rows in memory and wrote once at the end: a kill at 80% lost everything.)
OUTPUT_FIELDNAMES = [
    "id", "category", "subcategory", "question", "answer_type", "options", "tags",
    "target_field", "persona_id", "persona_name", "temperature", "generation_round",
    "split_type", "shared_group_id",
    "expert_role", "model_answer", "model_reasoning", "model_score_1_to_5",
    "predicted_fields", "field_scores_json", "confidence", "target_confirmed",
    "model_name", "prompt_version", "run_id", "timestamp_utc", "is_synthetic", "error",
]

_output_lock = threading.Lock()


def append_output_row(record: dict) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _output_lock:
        write_header = not OUTPUT_CSV.exists() or OUTPUT_CSV.stat().st_size == 0
        with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(record)


def make_generation_key(target_field: str, persona_id: str, question_id, split_type: str) -> str:
    qid = str(question_id)
    return f"{target_field}||{persona_id}||{split_type}||{qid}"


def select_candidate_rows(df: pd.DataFrame, field: str) -> pd.DataFrame:
    keywords = FIELD_KEYWORDS.get(field, [])
    text = (
        df["category"].fillna("").astype(str)
        + " "
        + df["subcategory"].fillna("").astype(str)
        + " "
        + df["tags"].fillna("").astype(str)
        + " "
        + df["question"].fillna("").astype(str)
    ).str.lower()
    if not keywords:
        return df
    mask = pd.Series(False, index=df.index)
    for kw in keywords:
        mask = mask | text.str.contains(kw.lower(), regex=False)
    filtered = df[mask]
    return filtered if not filtered.empty else df


def persona_temperature(slot_index_zero_based: int) -> float:
    return PERSONA_TEMPERATURES[slot_index_zero_based % len(PERSONA_TEMPERATURES)]


def build_generation_plan(df: pd.DataFrame) -> list[dict]:
    if GENERATION_MODE == "exhaustive":
        return build_exhaustive_plan(df)
    if GENERATION_MODE == "partitioned_shared_20":
        return build_partitioned_shared_plan(df)

    plan = []
    for field in CANONICAL_FIELDS:
        candidates = select_candidate_rows(df, field).reset_index(drop=True)
        personas = FIELD_PERSONAS.get(field, ["Domain Subject Matter Expert"])
        for i in range(MIN_SAMPLES_PER_FIELD):
            row = candidates.iloc[i % len(candidates)]
            persona = personas[i % len(personas)]
            plan.append(
                {
                    "target_field": field,
                    "persona_id": f"{field.replace(' ', '_').replace('/', '_').lower()}_{i + 1}",
                    "persona_name": persona,
                    "persona_temperature": persona_temperature(i),
                    "generation_round": i + 1,
                    "split_type": "balanced",
                    "shared_group_id": "",
                    "row": row,
                }
            )
    return plan


def build_partitioned_shared_plan(df: pd.DataFrame) -> list[dict]:
    plan = []
    total_questions = len(df)
    if total_questions == 0:
        return plan

    shared_count = max(1, int(total_questions * SHARED_QUESTION_RATIO))
    all_indices = list(df.index)

    for field_index, field in enumerate(CANONICAL_FIELDS):
        personas = FIELD_PERSONAS.get(field, ["Domain Subject Matter Expert"])[:PERSONAS_PER_FIELD]
        persona_count = len(personas)
        if persona_count == 0:
            continue

        rng = random.Random(RANDOM_SEED + field_index)
        shuffled_indices = all_indices.copy()
        rng.shuffle(shuffled_indices)

        shared_indices = shuffled_indices[:shared_count]
        unique_pool = shuffled_indices[shared_count:]
        unique_buckets = [[] for _ in range(persona_count)]
        for idx, row_index in enumerate(unique_pool):
            unique_buckets[idx % persona_count].append(row_index)

        shared_group_id = (
            f"{field.replace(' ', '_').replace('/', '_').lower()}_shared_{int(SHARED_QUESTION_RATIO * 100)}"
        )
        for p_idx, persona in enumerate(personas, start=1):
            persona_id = f"{field.replace(' ', '_').replace('/', '_').lower()}_{p_idx}"
            persona_temp = persona_temperature(p_idx - 1)
            for row_index in shared_indices:
                row = df.loc[row_index]
                plan.append(
                    {
                        "target_field": field,
                        "persona_id": persona_id,
                        "persona_name": persona,
                        "persona_temperature": persona_temp,
                        "generation_round": p_idx,
                        "split_type": "shared",
                        "shared_group_id": shared_group_id,
                        "row": row,
                    }
                )
            bucket = unique_buckets[p_idx - 1]
            if MAX_UNIQUE_PER_PERSONA is not None:
                bucket = bucket[:MAX_UNIQUE_PER_PERSONA]
            for row_index in bucket:
                row = df.loc[row_index]
                plan.append(
                    {
                        "target_field": field,
                        "persona_id": persona_id,
                        "persona_name": persona,
                        "persona_temperature": persona_temp,
                        "generation_round": p_idx,
                        "split_type": "unique",
                        "shared_group_id": "",
                        "row": row,
                    }
                )

    return plan


def build_exhaustive_plan(df: pd.DataFrame) -> list[dict]:
    plan = []
    for field in CANONICAL_FIELDS:
        personas = FIELD_PERSONAS.get(field, ["Domain Subject Matter Expert"])
        for p_idx, persona in enumerate(personas, start=1):
            for _, row in df.iterrows():
                plan.append(
                    {
                        "target_field": field,
                        "persona_id": f"{field.replace(' ', '_').replace('/', '_').lower()}_{p_idx}",
                        "persona_name": persona,
                        "persona_temperature": persona_temperature(p_idx - 1),
                        "generation_round": p_idx,
                        "split_type": "all",
                        "shared_group_id": "",
                        "row": row,
                    }
                )
    return plan


# ---------------------------------------------------------------- agreement stats
def fleiss_kappa(votes_by_item: list[list[str]], categories: list[str]) -> float:
    """Fleiss' kappa; requires the same number of raters per subject."""
    counts = np.array([
        [votes.count(cat) for cat in categories]
        for votes in votes_by_item
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


def write_agreement_report(out_df: pd.DataFrame) -> None:
    """Confirmation-rate bias check + shared-subset agreement, in the same spirit as
    panel_label_profiles.py's synthetic_agreement_report.md. Scoped to PROMPT_VERSION
    rows only: rows generated before v4.0.0 had target_field force-injected into
    predicted_fields, so their "confirmation" is an artifact of the old code, not a
    genuine model judgment, and would silently mask the bias this report exists to
    catch.
    """
    df = out_df.copy()
    df["predicted_fields_parsed"] = df["predicted_fields"].apply(
        lambda v: json.loads(v) if isinstance(v, str) else (v if isinstance(v, list) else [])
    )
    current = df[df.get("prompt_version", "") == PROMPT_VERSION].copy()
    legacy_count = len(df) - len(current)

    if current.empty:
        REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
        REPORT_MD.write_text(
            "# Question Bank Agreement Report\n\n"
            f"No rows found for the current prompt version (`{PROMPT_VERSION}`). "
            f"{legacy_count} legacy rows exist but predate honest target-field "
            "confirmation (target_field was force-injected into predicted_fields), "
            "so no bias diagnostic can be computed yet. Run a generation pass to "
            "populate current-version rows.\n",
            encoding="utf-8",
        )
        print(f"Wrote {REPORT_MD} (no current-version rows yet)")
        return

    current["target_confirmed"] = current.apply(
        lambda r: r["target_field"] in r["predicted_fields_parsed"], axis=1
    )

    confirmation_by_field = (
        current.groupby("target_field")["target_confirmed"].mean().reindex(CANONICAL_FIELDS)
    )
    overall_rate = float(current["target_confirmed"].mean())
    flagged_fields = [
        f for f in CANONICAL_FIELDS
        if pd.notna(confirmation_by_field.get(f)) and confirmation_by_field[f] < 0.5 * overall_rate
    ]

    # Shared-subset agreement: within a field, do that field's own personas agree on
    # whether the target field applies to the same shared question? Two-category
    # Fleiss kappa (confirmed / not_confirmed) over complete panels only.
    shared = current[current["split_type"] == "shared"]
    fleiss = float("nan")
    pairwise: dict[str, float] = {}
    complete_panel_count = 0
    if not shared.empty:
        categories = ["confirmed", "not_confirmed"]
        groups = shared.groupby(["target_field", "id"])
        votes_by_item = []
        by_persona_slot: dict[str, list[str]] = {}
        for (_, _), g in groups:
            if len(g) != PERSONAS_PER_FIELD:
                continue
            g = g.sort_values("persona_id")
            labels = ["confirmed" if v else "not_confirmed" for v in g["target_confirmed"]]
            votes_by_item.append(labels)
            complete_panel_count += 1
            for slot, (_, row) in enumerate(g.iterrows()):
                by_persona_slot.setdefault(f"persona_{slot + 1}", []).append(labels[slot])
        if votes_by_item:
            try:
                fleiss = fleiss_kappa(votes_by_item, categories)
            except ValueError:
                fleiss = float("nan")
            slot_ids = sorted(by_persona_slot)
            for a, b in combinations(slot_ids, 2):
                pairwise[f"{a} vs {b}"] = cohen_kappa(by_persona_slot[a], by_persona_slot[b], categories)

    def dist_table(series: pd.Series) -> str:
        lines = ["| field | confirmation rate |", "|---|---|"]
        for f in CANONICAL_FIELDS:
            v = series.get(f)
            lines.append(f"| {f} | {'n/a' if pd.isna(v) else f'{v:.1%}'} |")
        return "\n".join(lines)

    report = f"""# Question Bank Agreement Report — LLM Persona Silver Labels

> **These are SILVER labels produced by local LLM personas, not human expert ground
> truth.** Agreement numbers below measure consistency between personas sharing one
> base model ({MODEL_FAST}); they are NOT a human inter-expert noise ceiling. See
> data/docs/NEURAL_MATCHER_DESIGN.md and docs/matching-rework-plan.md for the same
> caveat applied to the career-matcher panel.

Generated: {now_utc()}  |  model: `{MODEL_FAST}`  |  prompt: `{PROMPT_VERSION}`  |  temperatures: {PERSONA_TEMPERATURES}

## Pool

- Rows on current prompt version (`{PROMPT_VERSION}`): **{len(current)}**
- Legacy rows (older prompt versions, target_field was force-injected -- excluded
  from this report): {legacy_count}

## Target-field confirmation rate (bias check)

Overall confirmation rate: **{overall_rate:.1%}** (share of rows where the model's own
`predicted_fields` included the field its persona was assigned to represent, with no
forcing).

{dist_table(confirmation_by_field)}

{"**Flagged fields (confirmation rate < 50% of overall mean -- likely coding-role bias):** " + ", ".join(flagged_fields) if flagged_fields else "No fields flagged below the 50%-of-mean threshold."}

## Shared-subset agreement (NOT human agreement)

Complete panels available (same field, same question, all {PERSONAS_PER_FIELD} personas answered): **{complete_panel_count}**

- Fleiss' kappa (confirmed / not_confirmed, {PERSONAS_PER_FIELD} raters): **{fleiss:.3f}**
{chr(10).join(f"- Cohen's kappa {k}: {v:.3f}" for k, v in pairwise.items()) if pairwise else "- (not enough complete panels for pairwise kappa)"}

Interpretation caution: personas share one base model, so a high kappa here means
self-consistency, not correctness. A kappa near 1.0 is a flag for persona
non-independence, not a quality guarantee -- same reading as the career panel's report.

## Gate-style checklist

- [ ] No field's confirmation rate is flagged above (no systematic coding-role bias)
- [ ] Fleiss kappa is neither near 0 (personas disagree randomly) nor suspiciously
      near 1.0 (personas are clones despite distinct temperatures)
- [ ] Manual spot check of a handful of rows in `{OUTPUT_CSV}` looks reasonable
"""
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_MD}")
    print(f"overall_confirmation_rate={overall_rate:.1%} fleiss_kappa={fleiss:.3f} flagged_fields={flagged_fields}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N plan items (smoke test).")
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        help="Skip generation; recompute the agreement report from the existing output CSV.",
    )
    args = parser.parse_args()

    if args.aggregate_only:
        if not OUTPUT_CSV.exists():
            raise FileNotFoundError(f"Cannot aggregate: {OUTPUT_CSV} does not exist yet.")
        write_agreement_report(pd.read_csv(OUTPUT_CSV))
        return

    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    df = pd.read_csv(INPUT_CSV)
    required_cols = {"id", "category", "subcategory", "question", "answer_type", "options", "tags"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    plan = build_generation_plan(df)
    if args.limit:
        plan = plan[: args.limit]
    existing_keys = set()
    if RESUME_FROM_EXISTING and OUTPUT_CSV.exists():
        # on_bad_lines="skip": if a prior run was killed mid-write, the final CSV line
        # may be a partial row -- tolerate it rather than aborting the resume.
        existing_df = pd.read_csv(OUTPUT_CSV, on_bad_lines="skip")
        required_resume_cols = {"target_field", "persona_id", "split_type", "id"}
        if required_resume_cols.issubset(set(existing_df.columns)):
            for _, ex in existing_df.iterrows():
                existing_keys.add(
                    make_generation_key(
                        target_field=str(ex.get("target_field", "")),
                        persona_id=str(ex.get("persona_id", "")),
                        question_id=ex.get("id"),
                        split_type=str(ex.get("split_type", "")),
                    )
                )
        else:
            print(
                "Resume requested but existing output is missing key columns. "
                "Starting fresh for this run."
            )
            existing_keys = set()

    if existing_keys:
        original_plan_size = len(plan)
        filtered_plan = []
        for item in plan:
            row = item["row"]
            key = make_generation_key(
                target_field=item["target_field"],
                persona_id=item["persona_id"],
                question_id=row.get("id"),
                split_type=item.get("split_type", ""),
            )
            if key not in existing_keys:
                filtered_plan.append(item)
        plan = filtered_plan
        print(
            f"Resume mode: skipping {original_plan_size - len(plan)} existing rows, "
            f"remaining {len(plan)}"
        )

    def _process_item(item: dict) -> dict:
        row = item["row"]
        target_field = item["target_field"]
        persona_name = item["persona_name"]
        persona_temp = item["persona_temperature"]
        answer_type = str(row.get("answer_type", "")).strip()
        expert_role = persona_name or choose_expert(
            str(row.get("category", "")),
            str(row.get("subcategory", "")),
            str(row.get("tags", "")),
        )
        prompt = build_prompt(expert_role, target_field, row)
        error_text = ""
        shaped = None
        used_model = ""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw_result = call_ollama(
                    prompt=prompt, model=MODEL_FAST, num_predict=NUM_PREDICT_FAST, temperature=persona_temp
                )
                shaped = validate_and_shape(raw_result, expert_role, answer_type, target_field)
                used_model = MODEL_FAST
                break
            except Exception as exc:
                error_text = f"attempt_{attempt}: {exc}"

        if shaped is None and USE_STRONG_FALLBACK:
            try:
                raw_result = call_ollama(
                    prompt=prompt, model=MODEL_STRONG, num_predict=NUM_PREDICT_STRONG, temperature=persona_temp
                )
                shaped = validate_and_shape(raw_result, expert_role, answer_type, target_field)
                used_model = MODEL_STRONG
            except Exception as exc:
                error_text = f"{error_text}; strong_fallback: {exc}" if error_text else f"strong_fallback: {exc}"

        if shaped is None:
            shaped = {
                "expert_role": expert_role,
                "model_answer": "",
                "model_reasoning": "",
                "model_score_1_to_5": None,
                "predicted_fields": json.dumps([], ensure_ascii=True),
                "field_scores_json": json.dumps({}, ensure_ascii=True),
                "confidence": 0.0,
                "target_confirmed": False,
            }
            append_failure({
                "run_id": run_id,
                "timestamp_utc": now_utc(),
                "question_id": row.get("id"),
                "target_field": target_field,
                "error": error_text or "unknown_error",
            })

        shaped.update({
            "id": row.get("id"),
            "category": row.get("category"),
            "subcategory": row.get("subcategory"),
            "question": row.get("question"),
            "answer_type": row.get("answer_type"),
            "options": row.get("options"),
            "tags": row.get("tags"),
        })
        shaped["target_field"] = target_field
        shaped["persona_id"] = item["persona_id"]
        shaped["persona_name"] = persona_name
        shaped["temperature"] = persona_temp
        shaped["generation_round"] = item["generation_round"]
        shaped["split_type"] = item.get("split_type", "")
        shaped["shared_group_id"] = item.get("shared_group_id", "")
        shaped["model_name"] = used_model or f"{MODEL_FAST}|failed"
        shaped["prompt_version"] = PROMPT_VERSION
        shaped["run_id"] = run_id
        shaped["timestamp_utc"] = now_utc()
        shaped["is_synthetic"] = 1
        shaped["error"] = error_text
        return shaped

    print(f"Generation mode: {GENERATION_MODE}")
    print(f"Planned generations: {len(plan)}  workers: {OLLAMA_WORKERS}")
    print(f"Checkpointing each row to {OUTPUT_CSV} as it completes (resumable on kill).")
    # Rows are appended to OUTPUT_CSV as each future resolves, so nothing is buffered
    # in memory waiting for a single end-of-run write. Consumed single-threaded here,
    # so append_output_row's lock is defensive, not contended.
    with ThreadPoolExecutor(max_workers=OLLAMA_WORKERS) as executor:
        futures = {executor.submit(_process_item, item): item for item in plan}
        for future in tqdm(as_completed(futures), total=len(plan), desc="Generating synthetic annotations"):
            append_output_row(future.result())

    if not OUTPUT_CSV.exists():
        print("No rows produced (empty plan?). Nothing to aggregate.")
        return
    out_df = pd.read_csv(OUTPUT_CSV, on_bad_lines="skip")
    coverage_counts = Counter(out_df["target_field"].astype(str).tolist())
    missing = [f for f in CANONICAL_FIELDS if coverage_counts.get(f, 0) < MIN_SAMPLES_PER_FIELD]
    if missing and args.limit is None:
        # Not fatal now that rows are already persisted: warn instead of raising so the
        # coverage summary + agreement report still run on whatever completed.
        print(f"WARNING: coverage gate not met (missing minimum samples for {missing}). "
              "Rerun to resume and fill the gaps.")
    if missing and args.limit is not None:
        print(f"Skipping coverage gate (--limit set): missing minimum samples for {missing}")
    print(f"Done. Rows in {OUTPUT_CSV}: {len(out_df)}")
    print(f"Run ID: {run_id}")
    print(f"Failure log: {FAILURES_JSONL}")
    print("Coverage summary:")
    for field in CANONICAL_FIELDS:
        print(f"- {field}: {coverage_counts.get(field, 0)}")

    write_agreement_report(out_df)


if __name__ == "__main__":
    main()
