import argparse
import re
from pathlib import Path

import pandas as pd


INPUT_CSV = Path("data/questions/question_bank.csv")
OUTPUT_CSV = Path("data/reports/question_bank_beginner_quality_flags.csv")
SUMMARY_MD = Path("data/reports/question_bank_beginner_quality_summary.md")

MAX_WORDS = 24
MAX_CHARS = 180

JARGON_TERMS = {
    "api",
    "sdk",
    "kpi",
    "etl",
    "llm",
    "mlops",
    "ci/cd",
    "oauth",
    "microservices",
    "a/b",
    "backlog",
    "roadmap",
    "wireframe",
}

LEADING_PATTERNS = [
    r"\b(obviously|clearly|of course)\b",
    r"\b(best|ideal)\b",
    r"\bshould\b",
]

AMBIGUOUS_PHRASES = [
    "most of the time",
    "typically",
    "overall",
    "when it matters",
    "this describes me well",
    "this is true for me",
    "i can relate to this",
]

FIELD_KEYWORDS = {
    "Frontend Development": ["ui", "interface", "web page", "css", "frontend", "layout"],
    "Backend Development": ["api", "database", "server", "backend", "service", "logic"],
    "Full Stack Development": ["frontend", "backend", "full stack", "end-to-end", "web app"],
    "Mobile Development": ["mobile", "android", "ios", "app", "phone", "tablet"],
    "Data Analysis": ["data", "dashboard", "report", "insight", "metrics", "analysis"],
    "Data Science": ["statistics", "hypothesis", "experiment", "dataset", "modeling"],
    "Machine Learning": ["machine learning", "train model", "prediction", "features", "inference"],
    "AI Engineering": ["llm", "ai", "prompt", "agent", "embedding", "model deployment"],
    "Cyber Security": ["security", "threat", "risk", "vulnerability", "access", "incident"],
    "DevOps": ["deployment", "infrastructure", "automation", "ci/cd", "reliability", "monitoring"],
    "QA / Software Testing": ["test", "bug", "quality", "validation", "edge case"],
    "Game Development": ["game", "gameplay", "engine", "player", "level design"],
    "UI / UX Design": ["ux", "ui", "design", "prototype", "usability", "user journey"],
    "Product Management": ["product", "roadmap", "prioritize", "stakeholder", "outcome"],
    "Technical Writing": ["document", "guide", "explain", "manual", "instruction"],
    "Software Architecture": ["architecture", "scalability", "system design", "trade-off", "modular"],
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z]{3,}", normalize_text(value)))


def score_question(row: pd.Series) -> dict:
    question = str(row.get("question", ""))
    category = str(row.get("category", ""))
    subcategory = str(row.get("subcategory", ""))
    tags = str(row.get("tags", ""))

    reasons: list[str] = []
    score = 100

    q_norm = normalize_text(question)
    q_tokens = tokenize(question)
    axis_tokens = tokenize(f"{category} {subcategory} {tags}")

    # 1) Beginner-safe language.
    found_jargon = [term for term in JARGON_TERMS if term in q_norm]
    if found_jargon:
        score -= 10
        reasons.append(f"Contains jargon/acronym not explained: {', '.join(found_jargon[:3])}")

    # 2) Field discriminativeness.
    matched_fields = 0
    for keywords in FIELD_KEYWORDS.values():
        if any(keyword in q_norm for keyword in keywords):
            matched_fields += 1
    if matched_fields == 0:
        score -= 12
        reasons.append("Low field discriminativeness: no clear field signal words")
    elif matched_fields > 4:
        score -= 8
        reasons.append("Potential overlap: wording may point to too many different fields")

    # 3) Construct alignment with category/subcategory/tags axis.
    if axis_tokens and len(q_tokens.intersection(axis_tokens)) == 0:
        score -= 12
        reasons.append("Weak construct alignment with category/subcategory/tags axis")

    # 4) Ambiguity and leading wording.
    leading_hits = [p for p in LEADING_PATTERNS if re.search(p, q_norm)]
    if leading_hits:
        score -= 8
        reasons.append("Potential leading wording")

    ambiguity_hits = [phrase for phrase in AMBIGUOUS_PHRASES if phrase in q_norm]
    if ambiguity_hits:
        score -= 8
        reasons.append("Contains hedging boilerplate that can reduce clarity")

    # 5) Answerability for inexperienced users.
    if " at work" in q_norm or "when learning" in q_norm or "in a team" in q_norm:
        score -= 6
        reasons.append("Scenario may exclude beginners without relevant context")

    # 6) Readability and length.
    word_count = len(re.findall(r"\b\w+\b", question))
    char_count = len(question)
    if word_count > MAX_WORDS:
        score -= 8
        reasons.append(f"Too long for quick comprehension ({word_count} words)")
    if char_count > MAX_CHARS:
        score -= 6
        reasons.append(f"Too long by characters ({char_count})")
    if question.strip() and question.strip()[0].islower():
        score -= 4
        reasons.append("Sentence casing issue lowers readability")

    # 7) Diversity check for near duplicates (lightweight).
    duplicate_markers = ["this describes me well", "this is true for me", "i can relate to this"]
    duplicate_marker_count = sum(1 for marker in duplicate_markers if marker in q_norm)
    if duplicate_marker_count > 0:
        score -= 6
        reasons.append("Template variant likely near-duplicate")

    score = max(0, min(100, score))
    severity = "ok"
    if score < 70:
        severity = "high"
    elif score < 82:
        severity = "medium"

    return {
        "quality_score": score,
        "severity": severity,
        "flagged": int(severity != "ok"),
        "reasons": " | ".join(reasons),
        "word_count": word_count,
        "char_count": char_count,
    }


def build_summary(df: pd.DataFrame, flagged_df: pd.DataFrame) -> str:
    total = len(df)
    flagged = len(flagged_df)
    high = int((flagged_df["severity"] == "high").sum()) if flagged else 0
    medium = int((flagged_df["severity"] == "medium").sum()) if flagged else 0

    lines = []
    lines.append("# Beginner Field-Detection Question Quality Summary")
    lines.append("")
    lines.append(f"- Input rows: `{total}`")
    lines.append(f"- Flagged rows: `{flagged}`")
    lines.append(f"- High severity flags: `{high}`")
    lines.append(f"- Medium severity flags: `{medium}`")
    lines.append("")
    lines.append("## Top recurring issues")
    if flagged == 0:
        lines.append("- No flagged issues.")
    else:
        issue_counts: dict[str, int] = {}
        for reasons in flagged_df["reasons"].fillna("").astype(str):
            for reason in [r.strip() for r in reasons.split("|") if r.strip()]:
                issue_counts[reason] = issue_counts.get(reason, 0) + 1
        for reason, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"- {reason}: `{count}`")
    lines.append("")
    lines.append(f"Detailed flags CSV: `{OUTPUT_CSV}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit beginner-facing question quality.")
    parser.add_argument("--input", type=Path, default=INPUT_CSV, help="Input question bank CSV path.")
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV, help="Output flagged review CSV path.")
    parser.add_argument("--summary", type=Path, default=SUMMARY_MD, help="Output summary markdown path.")
    parser.add_argument("--flag-threshold", type=int, default=82, help="Score threshold below which rows are flagged.")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    df = pd.read_csv(args.input)
    required = {"id", "category", "subcategory", "question", "answer_type", "options", "tags"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    scored_rows = []
    for _, row in df.iterrows():
        scores = score_question(row)
        flagged = int(scores["quality_score"] < args.flag_threshold)
        scores["flagged"] = flagged
        scored_rows.append(scores)
    scored_df = pd.DataFrame(scored_rows)

    out_df = pd.concat([df, scored_df], axis=1)
    flagged_df = out_df[out_df["flagged"] == 1].copy()
    flagged_df.sort_values(by=["quality_score", "id"], ascending=[True, True], inplace=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    flagged_df.to_csv(args.output, index=False)
    args.summary.write_text(build_summary(out_df, flagged_df), encoding="utf-8")

    print(f"Wrote flagged review CSV: {args.output}")
    print(f"Wrote summary report: {args.summary}")
    print(f"Flagged rows: {len(flagged_df)} / {len(out_df)}")


if __name__ == "__main__":
    main()
