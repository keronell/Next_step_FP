import json
import random
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


INPUT_CSV = Path("data/data/question_bank.csv")
OUTPUT_CSV = Path("data/data/question_bank_answered_local.csv")
FAILURES_JSONL = Path("data/data/annotation_failures.jsonl")
MODEL_FAST = "qwen2.5:7b-instruct"
MODEL_STRONG = "qwen3:14b"
USE_STRONG_FALLBACK = False
OLLAMA_URL = "http://localhost:11434/api/generate"
PROMPT_VERSION = "v3.0.0"
MAX_RETRIES = 1
NUM_PREDICT_FAST = 120
NUM_PREDICT_STRONG = 220
MIN_SAMPLES_PER_FIELD = 5
GENERATION_MODE = "partitioned_shared_20"  # "balanced", "exhaustive", or "partitioned_shared_20"
SHARED_QUESTION_RATIO = 0.20
RANDOM_SEED = 42
RESUME_FROM_EXISTING = True

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

    return f"""
You are a {expert_role}.
You are generating synthetic annotation data for an adaptive questionnaire experiment.
Answer only as that expert.
Primary target field for this sample: {target_field}

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
1) Keep `predicted_fields` length between 3 and 5.
2) Ensure `{target_field}` is included in `predicted_fields`.
2) `predicted_fields` values must come only from this list: {fields_json}
3) `field_scores` must include all 16 fields from the same list.
4) `field_scores` values must be numeric in [0, 1].
5) If `answer_type` is Likert5, set `score_1_to_5` as integer 1..5; otherwise set null.
6) Keep `reasoning` to 1 short sentence.
7) Keep `confidence` in [0,1].

Context:
- Category: {category}
- Subcategory: {subcategory}
- Tags: {tags}
- Answer type: {answer_type}
- Options: {options}

Question:
{question}
""".strip()


def call_ollama(prompt: str, model: str, num_predict: int, timeout_s: int = 180) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": num_predict,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout_s)
    response.raise_for_status()
    raw = response.json().get("response", "").strip()
    return json.loads(raw)


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
    if target_field not in cleaned_predicted:
        cleaned_predicted = [target_field] + cleaned_predicted
        cleaned_predicted = list(dict.fromkeys(cleaned_predicted))
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
    }


def append_failure(record: dict) -> None:
    FAILURES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    serializable_record = {
        k: (v.item() if hasattr(v, "item") else v)
        for k, v in record.items()
    }
    with FAILURES_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(serializable_record, ensure_ascii=True, default=str) + "\n")


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
        personas = FIELD_PERSONAS.get(field, ["Domain Subject Matter Expert"])
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
            for row_index in shared_indices:
                row = df.loc[row_index]
                plan.append(
                    {
                        "target_field": field,
                        "persona_id": persona_id,
                        "persona_name": persona,
                        "generation_round": p_idx,
                        "split_type": "shared",
                        "shared_group_id": shared_group_id,
                        "row": row,
                    }
                )
            for row_index in unique_buckets[p_idx - 1]:
                row = df.loc[row_index]
                plan.append(
                    {
                        "target_field": field,
                        "persona_id": persona_id,
                        "persona_name": persona,
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
                        "generation_round": p_idx,
                        "split_type": "all",
                        "shared_group_id": "",
                        "row": row,
                    }
                )
    return plan


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    df = pd.read_csv(INPUT_CSV)
    required_cols = {"id", "category", "subcategory", "question", "answer_type", "options", "tags"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    plan = build_generation_plan(df)
    outputs = []
    existing_df = pd.DataFrame()
    existing_keys = set()
    if RESUME_FROM_EXISTING and OUTPUT_CSV.exists():
        existing_df = pd.read_csv(OUTPUT_CSV)
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
            existing_df = pd.DataFrame()
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

    print(f"Generation mode: {GENERATION_MODE}")
    print(f"Planned generations: {len(plan)}")
    for item in tqdm(plan, total=len(plan), desc="Generating synthetic annotations"):
        row = item["row"]
        target_field = item["target_field"]
        persona_name = item["persona_name"]
        answer_type = str(row.get("answer_type", "")).strip()

        # Prefer field persona; fallback to heuristic domain expert selection.
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
                    prompt=prompt,
                    model=MODEL_FAST,
                    num_predict=NUM_PREDICT_FAST,
                )
                shaped = validate_and_shape(raw_result, expert_role, answer_type, target_field)
                used_model = MODEL_FAST
                break
            except Exception as exc:
                error_text = f"attempt_{attempt}: {exc}"

        if shaped is None and USE_STRONG_FALLBACK:
            try:
                raw_result = call_ollama(
                    prompt=prompt,
                    model=MODEL_STRONG,
                    num_predict=NUM_PREDICT_STRONG,
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
            }
            append_failure(
                {
                    "run_id": run_id,
                    "timestamp_utc": now_utc(),
                    "question_id": row.get("id"),
                    "target_field": target_field,
                    "error": error_text or "unknown_error",
                }
            )

        base = {
            "id": row.get("id"),
            "category": row.get("category"),
            "subcategory": row.get("subcategory"),
            "question": row.get("question"),
            "answer_type": row.get("answer_type"),
            "options": row.get("options"),
            "tags": row.get("tags"),
        }
        shaped.update(base)
        shaped["target_field"] = target_field
        shaped["persona_id"] = item["persona_id"]
        shaped["persona_name"] = persona_name
        shaped["generation_round"] = item["generation_round"]
        shaped["split_type"] = item.get("split_type", "")
        shaped["shared_group_id"] = item.get("shared_group_id", "")
        shaped["model_name"] = used_model or f"{MODEL_FAST}|failed"
        shaped["prompt_version"] = PROMPT_VERSION
        shaped["run_id"] = run_id
        shaped["timestamp_utc"] = now_utc()
        shaped["is_synthetic"] = 1
        shaped["error"] = error_text
        outputs.append(shaped)

    new_df = pd.DataFrame(outputs)
    out_df = pd.concat([existing_df, new_df], ignore_index=True) if not existing_df.empty else new_df
    coverage_counts = Counter(out_df["target_field"].astype(str).tolist())
    missing = [f for f in CANONICAL_FIELDS if coverage_counts.get(f, 0) < MIN_SAMPLES_PER_FIELD]
    if missing:
        raise RuntimeError(
            f"Coverage check failed. Missing minimum samples for fields: {missing}"
        )
    out_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Done. Wrote: {OUTPUT_CSV}")
    print(f"Run ID: {run_id}")
    print(f"Failure log: {FAILURES_JSONL}")
    print("Coverage summary:")
    for field in CANONICAL_FIELDS:
        print(f"- {field}: {coverage_counts.get(field, 0)}")


if __name__ == "__main__":
    main()