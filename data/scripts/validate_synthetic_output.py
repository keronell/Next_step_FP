import json
from pathlib import Path

import pandas as pd


INPUT_CSV = Path("data/data/question_bank_answered_local.csv")
REPORT_MD = Path("data/reports/synthetic_output_validation_report.md")
REPORT_JSON = Path("data/reports/synthetic_output_validation_report.json")
MIN_SAMPLES_PER_FIELD = 2

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


def parse_json_cell(value):
    if pd.isna(value):
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)
    total_rows = len(df)
    if total_rows == 0:
        raise ValueError("Input CSV has no rows.")

    required_cols = [
        "predicted_fields",
        "field_scores_json",
        "confidence",
        "error",
        "model_score_1_to_5",
        "answer_type",
        "question",
        "target_field",
        "persona_id",
        "persona_name",
        "generation_round",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in input: {missing}")

    parsed_predicted = df["predicted_fields"].apply(parse_json_cell)
    parsed_scores = df["field_scores_json"].apply(parse_json_cell)

    valid_predicted_json = int(parsed_predicted.notna().sum())
    valid_scores_json = int(parsed_scores.notna().sum())

    def is_valid_topk(v):
        if not isinstance(v, list):
            return False
        if not (3 <= len(v) <= 5):
            return False
        if len(v) != len(set(v)):
            return False
        return all(isinstance(x, str) and x in CANONICAL_FIELDS for x in v)

    topk_valid_count = int(parsed_predicted.apply(is_valid_topk).sum())

    def score_dict_valid(v):
        if not isinstance(v, dict):
            return False
        if set(v.keys()) != set(CANONICAL_FIELDS):
            return False
        try:
            vals = [float(v[k]) for k in CANONICAL_FIELDS]
        except Exception:
            return False
        if any(x < 0 or x > 1 for x in vals):
            return False
        s = sum(vals)
        return abs(s - 1.0) <= 1e-3

    score_dict_valid_count = int(parsed_scores.apply(score_dict_valid).sum())

    confidence = pd.to_numeric(df["confidence"], errors="coerce")
    confidence_valid = confidence.between(0, 1, inclusive="both")
    confidence_valid_count = int(confidence_valid.sum())
    confidence_mean = float(confidence[confidence_valid].mean()) if confidence_valid_count else 0.0

    err_col = df["error"].fillna("").astype(str).str.strip()
    rows_with_error = int((err_col != "").sum())

    likert_mask = df["answer_type"].astype(str).str.strip().str.lower() == "likert5"
    likert_total = int(likert_mask.sum())
    likert_scores = pd.to_numeric(df.loc[likert_mask, "model_score_1_to_5"], errors="coerce")
    likert_valid = likert_scores.isin([1, 2, 3, 4, 5])
    likert_valid_count = int(likert_valid.sum())

    parse_failed_mask = parsed_predicted.isna() | parsed_scores.isna()
    top_fail = (
        df.loc[parse_failed_mask, ["id", "question", "error"]]
        .head(20)
        .fillna("")
        .to_dict(orient="records")
    )

    field_hits = {f: 0 for f in CANONICAL_FIELDS}
    for items in parsed_predicted:
        if isinstance(items, list):
            for field in items:
                if field in field_hits:
                    field_hits[field] += 1

    target_field_counts = (
        df["target_field"].fillna("").astype(str).value_counts().to_dict()
    )
    target_field_coverage = {f: int(target_field_counts.get(f, 0)) for f in CANONICAL_FIELDS}
    fields_below_min_target = [f for f, c in target_field_coverage.items() if c < MIN_SAMPLES_PER_FIELD]

    target_field_valid_rows = int(df["target_field"].isin(CANONICAL_FIELDS).sum())

    persona_diversity = {}
    fields_low_persona_diversity = []
    for field in CANONICAL_FIELDS:
        scoped = df[df["target_field"] == field]
        unique_personas = (
            scoped["persona_name"].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().nunique()
        )
        persona_diversity[field] = int(unique_personas)
        expected_personas = 2 if len(scoped) >= 2 else 1
        if unique_personas < expected_personas:
            fields_low_persona_diversity.append(field)

    target_in_predicted_count = 0
    for target, pred in zip(df["target_field"].tolist(), parsed_predicted.tolist()):
        if isinstance(pred, list) and isinstance(target, str) and target in pred:
            target_in_predicted_count += 1

    summary = {
        "input_csv": str(INPUT_CSV),
        "total_rows": total_rows,
        "valid_predicted_fields_json_rows": valid_predicted_json,
        "valid_field_scores_json_rows": valid_scores_json,
        "valid_topk_rows": topk_valid_count,
        "valid_score_dict_rows": score_dict_valid_count,
        "confidence_valid_rows": confidence_valid_count,
        "confidence_mean_valid_rows": round(confidence_mean, 4),
        "rows_with_error_text": rows_with_error,
        "likert_rows": likert_total,
        "likert_rows_with_valid_score": likert_valid_count,
        "field_coverage_counts": field_hits,
        "target_field_valid_rows": target_field_valid_rows,
        "target_field_coverage_counts": target_field_coverage,
        "fields_below_min_samples_target_field": fields_below_min_target,
        "min_samples_per_field_required": MIN_SAMPLES_PER_FIELD,
        "persona_diversity_by_field": persona_diversity,
        "fields_with_low_persona_diversity": fields_low_persona_diversity,
        "rows_where_target_field_appears_in_predicted_fields": target_in_predicted_count,
        "sample_failed_rows": top_fail,
    }

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")

    md = []
    md.append("# Synthetic Output Validation Report")
    md.append("")
    md.append(f"- Input file: `{INPUT_CSV}`")
    md.append(f"- Total rows: `{total_rows}`")
    md.append("")
    md.append("## Core Checks")
    md.append(f"- Valid `predicted_fields` JSON rows: `{valid_predicted_json}/{total_rows}`")
    md.append(f"- Valid `field_scores_json` JSON rows: `{valid_scores_json}/{total_rows}`")
    md.append(f"- Valid top-k rows (3-5 canonical fields): `{topk_valid_count}/{total_rows}`")
    md.append(f"- Valid score dictionaries (all 16 fields + sums to ~1): `{score_dict_valid_count}/{total_rows}`")
    md.append(f"- Confidence in [0,1]: `{confidence_valid_count}/{total_rows}`")
    md.append(f"- Mean confidence (valid rows): `{round(confidence_mean, 4)}`")
    md.append(f"- Rows with non-empty `error`: `{rows_with_error}`")
    md.append("")
    md.append("## Likert5 Score Check")
    md.append(f"- Likert5 rows: `{likert_total}`")
    md.append(f"- Likert5 rows with score in [1..5]: `{likert_valid_count}/{likert_total if likert_total else 1}`")
    md.append("")
    md.append("## Field Coverage (predicted_fields frequency)")
    for f in CANONICAL_FIELDS:
        md.append(f"- {f}: `{field_hits[f]}`")
    md.append("")
    md.append("## Target Field Coverage (generation guarantee)")
    md.append(f"- Target field valid rows: `{target_field_valid_rows}/{total_rows}`")
    md.append(f"- Rows where `target_field` appears in `predicted_fields`: `{target_in_predicted_count}/{total_rows}`")
    md.append(f"- Minimum samples required per field: `{MIN_SAMPLES_PER_FIELD}`")
    for f in CANONICAL_FIELDS:
        md.append(f"- {f}: `{target_field_coverage[f]}`")
    if fields_below_min_target:
        md.append(f"- Fields below minimum target samples: `{fields_below_min_target}`")
    else:
        md.append("- Fields below minimum target samples: `[]`")
    md.append("")
    md.append("## Persona Diversity by Field")
    for f in CANONICAL_FIELDS:
        md.append(f"- {f}: `{persona_diversity[f]}` unique personas")
    if fields_low_persona_diversity:
        md.append(f"- Fields with low persona diversity: `{fields_low_persona_diversity}`")
    else:
        md.append("- Fields with low persona diversity: `[]`")
    md.append("")
    md.append("## Sample Failed Rows (up to 20)")
    if not top_fail:
        md.append("- No parse failures detected.")
    else:
        for item in top_fail:
            q = str(item.get("question", ""))[:120].replace("\n", " ")
            md.append(
                f"- id=`{item.get('id', '')}` | error=`{item.get('error', '')}` | question=`{q}`"
            )
    md.append("")
    md.append(f"Raw JSON summary: `{REPORT_JSON}`")
    REPORT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"Done. Wrote {REPORT_MD}")
    print(f"Done. Wrote {REPORT_JSON}")


if __name__ == "__main__":
    main()
