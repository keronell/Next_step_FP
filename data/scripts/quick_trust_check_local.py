import argparse
import json
import random
from pathlib import Path

import pandas as pd
import requests


QUESTION_BANK_CSV = Path("data/questions/question_bank.csv")
OUTPUT_CSV = Path("data/reports/quick_trust_check_results.csv")
OUTPUT_MD = Path("data/reports/quick_trust_check_report.md")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b-instruct"

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

FIELD_KEYWORDS = {
    "Frontend Development": ["frontend", "ui", "ux", "interface", "css", "web"],
    "Backend Development": ["backend", "api", "database", "server", "service"],
    "Full Stack Development": ["full stack", "frontend", "backend", "web app"],
    "Mobile Development": ["mobile", "android", "ios", "app"],
    "Data Analysis": ["analytics", "dashboard", "insight", "report", "metric"],
    "Data Science": ["statistics", "experiment", "modeling", "hypothesis"],
    "Machine Learning": ["machine learning", "training", "inference", "feature"],
    "AI Engineering": ["ai", "llm", "prompt", "agent", "embedding"],
    "Cyber Security": ["security", "threat", "vulnerability", "incident", "access"],
    "DevOps": ["devops", "deployment", "infrastructure", "ci/cd", "reliability"],
    "QA / Software Testing": ["qa", "testing", "test", "bug", "validation"],
    "Game Development": ["game", "gameplay", "unity", "unreal", "engine"],
    "UI / UX Design": ["ux", "ui", "design", "prototype", "usability"],
    "Product Management": ["product", "roadmap", "stakeholder", "prioritization"],
    "Technical Writing": ["documentation", "docs", "guide", "manual", "writing"],
    "Software Architecture": ["architecture", "system design", "scalability", "distributed"],
}


def infer_target_field(text: str) -> str:
    text = str(text).lower()
    for field in CANONICAL_FIELDS:
        keywords = FIELD_KEYWORDS.get(field, [])
        if any(keyword in text for keyword in keywords):
            return field
    return "Full Stack Development"


def build_prompt(row: pd.Series, target_field: str) -> str:
    fields_json = json.dumps(CANONICAL_FIELDS, ensure_ascii=True)
    return f"""
You are answering one questionnaire item as an experienced professional.
Target field for consistency check: {target_field}

Return strict JSON only with this schema:
{{
  "final_answer": "string",
  "reasoning": "string",
  "score_1_to_5": 1,
  "predicted_fields": ["string", "string", "string"],
  "field_scores": {{"Frontend Development": 0.01}},
  "confidence": 0.0
}}

Rules:
1) Use only these fields: {fields_json}
2) `predicted_fields` must be 3 to 5 unique canonical fields.
3) `field_scores` must include all canonical fields with numeric values in [0,1].
4) Confidence must be in [0,1].
5) Keep reasoning short and concrete.
6) If answer_type is Likert5 set score_1_to_5 from 1..5, else set null.

Question context:
- Category: {row.get("category", "")}
- Subcategory: {row.get("subcategory", "")}
- Answer type: {row.get("answer_type", "")}
- Options: {row.get("options", "")}
- Tags: {row.get("tags", "")}

Question:
{row.get("question", "")}
""".strip()


def call_ollama_json(prompt: str, model: str, num_predict: int, timeout_s: int) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": num_predict},
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout_s)
    response.raise_for_status()
    raw = response.json().get("response", "")
    return json.loads(raw)


def validate_result(result: dict, answer_type: str, target_field: str) -> dict:
    checks = {
        "json_valid": 1,
        "schema_valid": 1,
        "predicted_fields_valid": 1,
        "field_scores_valid": 1,
        "target_field_consistency": 1,
        "confidence_sanity": 1,
        "likert_score_valid": 1,
        "format_contradiction_check": 1,
    }
    reasons: list[str] = []

    if not isinstance(result, dict):
        for key in checks:
            checks[key] = 0
        reasons.append("Output is not a JSON object.")
        return {"checks": checks, "issues": reasons}

    required = {"final_answer", "reasoning", "score_1_to_5", "predicted_fields", "field_scores", "confidence"}
    if not required.issubset(result.keys()):
        checks["schema_valid"] = 0
        reasons.append("Missing required keys in JSON schema.")

    predicted = result.get("predicted_fields")
    if not isinstance(predicted, list) or not (3 <= len(predicted) <= 5) or len(set(predicted)) != len(predicted):
        checks["predicted_fields_valid"] = 0
        reasons.append("predicted_fields must be 3-5 unique values.")
    elif any((not isinstance(p, str)) or (p not in CANONICAL_FIELDS) for p in predicted):
        checks["predicted_fields_valid"] = 0
        reasons.append("predicted_fields contains unknown values.")

    field_scores = result.get("field_scores")
    if not isinstance(field_scores, dict) or set(field_scores.keys()) != set(CANONICAL_FIELDS):
        checks["field_scores_valid"] = 0
        reasons.append("field_scores does not include exact canonical field set.")
    else:
        try:
            values = [float(field_scores[k]) for k in CANONICAL_FIELDS]
            if any(v < 0 or v > 1 for v in values):
                checks["field_scores_valid"] = 0
                reasons.append("field_scores has values outside [0,1].")
        except (TypeError, ValueError):
            checks["field_scores_valid"] = 0
            reasons.append("field_scores has non-numeric values.")

    confidence = result.get("confidence")
    try:
        confidence = float(confidence)
        if confidence < 0 or confidence > 1:
            checks["confidence_sanity"] = 0
            reasons.append("confidence outside [0,1].")
    except (TypeError, ValueError):
        checks["confidence_sanity"] = 0
        reasons.append("confidence is non-numeric.")
        confidence = 0.0

    if isinstance(predicted, list):
        if target_field not in predicted:
            checks["target_field_consistency"] = 0
            reasons.append("target_field missing from predicted_fields.")

    score_1_to_5 = result.get("score_1_to_5")
    if str(answer_type).strip().lower() == "likert5":
        if score_1_to_5 not in [1, 2, 3, 4, 5]:
            checks["likert_score_valid"] = 0
            reasons.append("Likert question has invalid score_1_to_5.")
    else:
        if score_1_to_5 is not None:
            checks["likert_score_valid"] = 0
            reasons.append("Non-Likert question should have null score_1_to_5.")

    reasoning = str(result.get("reasoning", ""))
    answer = str(result.get("final_answer", ""))
    if len(reasoning.split()) > 25:
        checks["format_contradiction_check"] = 0
        reasons.append("Reasoning too long for concise format.")
    if confidence >= 0.9 and checks["target_field_consistency"] == 0:
        checks["format_contradiction_check"] = 0
        reasons.append("High confidence conflicts with target inconsistency.")
    if not answer.strip():
        checks["format_contradiction_check"] = 0
        reasons.append("final_answer is empty.")

    passed = int(all(v == 1 for v in checks.values()))
    return {"checks": checks, "issues": reasons, "passed": passed}


def run_quick_check(
    input_csv: Path,
    output_csv: Path,
    output_md: Path,
    sample_size: int,
    seed: int,
    model: str,
    num_predict: int,
    timeout_s: int,
    skip_model_call: bool,
) -> None:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input file not found: {input_csv}")

    df = pd.read_csv(input_csv)
    required = {"id", "category", "subcategory", "question", "answer_type", "options", "tags"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    sample_n = min(sample_size, len(df))
    sampled = df.sample(n=sample_n, random_state=seed).reset_index(drop=True)
    records = []

    for _, row in sampled.iterrows():
        row_text = " ".join([str(row.get("category", "")), str(row.get("subcategory", "")), str(row.get("tags", ""))])
        target_field = infer_target_field(row_text)
        prompt = build_prompt(row, target_field)

        record = {
            "id": row.get("id"),
            "question": row.get("question"),
            "answer_type": row.get("answer_type"),
            "target_field": target_field,
            "model_name": model,
            "error": "",
            "trust_pass": 0,
            "issues": "",
        }

        if skip_model_call:
            record["error"] = "Skipped model call by configuration."
            records.append(record)
            continue

        try:
            result = call_ollama_json(prompt=prompt, model=model, num_predict=num_predict, timeout_s=timeout_s)
            validation = validate_result(result, answer_type=str(row.get("answer_type", "")), target_field=target_field)
            record["json_valid"] = validation["checks"]["json_valid"]
            record["schema_valid"] = validation["checks"]["schema_valid"]
            record["predicted_fields_valid"] = validation["checks"]["predicted_fields_valid"]
            record["field_scores_valid"] = validation["checks"]["field_scores_valid"]
            record["target_field_consistency"] = validation["checks"]["target_field_consistency"]
            record["confidence_sanity"] = validation["checks"]["confidence_sanity"]
            record["likert_score_valid"] = validation["checks"]["likert_score_valid"]
            record["format_contradiction_check"] = validation["checks"]["format_contradiction_check"]
            record["trust_pass"] = validation["passed"]
            record["issues"] = " | ".join(validation["issues"])
        except Exception as exc:
            record["json_valid"] = 0
            record["schema_valid"] = 0
            record["predicted_fields_valid"] = 0
            record["field_scores_valid"] = 0
            record["target_field_consistency"] = 0
            record["confidence_sanity"] = 0
            record["likert_score_valid"] = 0
            record["format_contradiction_check"] = 0
            record["error"] = str(exc)
            record["issues"] = "Model call or JSON parse failed."

        records.append(record)

    out_df = pd.DataFrame(records)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_csv, index=False)

    total = len(out_df)
    pass_count = int(out_df["trust_pass"].sum()) if "trust_pass" in out_df.columns else 0
    fail_count = total - pass_count
    model_errors = int((out_df["error"].fillna("").astype(str).str.strip() != "").sum())

    lines = [
        "# Quick Local Trust Check Report",
        "",
        f"- Input file: `{input_csv}`",
        f"- Sample size requested: `{sample_size}`",
        f"- Sample size executed: `{total}`",
        f"- Model: `{model}`",
        f"- Trust pass rows: `{pass_count}`",
        f"- Trust fail rows: `{fail_count}`",
        f"- Rows with model/parse errors: `{model_errors}`",
        "",
        "## Check pass rates",
    ]

    check_columns = [
        "json_valid",
        "schema_valid",
        "predicted_fields_valid",
        "field_scores_valid",
        "target_field_consistency",
        "confidence_sanity",
        "likert_score_valid",
        "format_contradiction_check",
    ]
    for col in check_columns:
        if col in out_df.columns:
            lines.append(f"- {col}: `{int(out_df[col].sum())}/{total}`")
    lines.extend(
        [
            "",
            "## Sample failed rows",
        ]
    )
    failed_rows = out_df[out_df["trust_pass"] == 0].head(10)
    if failed_rows.empty:
        lines.append("- No failed rows in sampled set.")
    else:
        for _, fr in failed_rows.iterrows():
            q = str(fr.get("question", ""))[:110].replace("\n", " ")
            lines.append(f"- id=`{fr.get('id')}` | issues=`{fr.get('issues', '')}` | question=`{q}`")
    lines.append("")
    lines.append(f"Detailed CSV: `{output_csv}`")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote: {output_csv}")
    print(f"Wrote: {output_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fast trust check on a small sample via local Ollama model.")
    parser.add_argument("--input", type=Path, default=QUESTION_BANK_CSV, help="Question bank CSV.")
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV, help="Output diagnostic CSV.")
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD, help="Output markdown report.")
    parser.add_argument("--sample-size", type=int, default=30, help="Small sample size for fast trust checks.")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed.")
    parser.add_argument("--model", type=str, default=MODEL_NAME, help="Ollama model name.")
    parser.add_argument("--num-predict", type=int, default=110, help="Generation token budget.")
    parser.add_argument("--timeout-s", type=int, default=90, help="Per-request timeout.")
    parser.add_argument(
        "--skip-model-call",
        action="store_true",
        help="Skip calling Ollama (pipeline dry-run only).",
    )
    args = parser.parse_args()

    run_quick_check(
        input_csv=args.input,
        output_csv=args.output_csv,
        output_md=args.output_md,
        sample_size=args.sample_size,
        seed=args.seed,
        model=args.model,
        num_predict=args.num_predict,
        timeout_s=args.timeout_s,
        skip_model_call=args.skip_model_call,
    )


if __name__ == "__main__":
    main()
