"""
Skill extractor — reads raw job ads JSON and adds a normalized `skills` list
to each job using regex pattern matching + optional Ollama LLM fallback.

Usage:
    python data/scripts/extract_skills.py
    python data/scripts/extract_skills.py --use-llm          # enrich with Ollama
    python data/scripts/extract_skills.py --sources remoteok  # single source
"""

import argparse
import json
import re
import time
from pathlib import Path

import requests

CONFIG_DIR = Path("data/config")
JOB_ADS_DIR = Path("data/jobs/raw")
ALIASES_FILE = CONFIG_DIR / "skill_aliases.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_TIMEOUT = 30

# Canonical skill patterns — (regex, canonical_name)
# Order matters: more specific patterns first
SKILL_PATTERNS: list[tuple[str, str]] = [
    # Languages
    (r"\btypescript\b", "TypeScript"),
    (r"\bjavascript\b|\bjs\b(?!on)", "JavaScript"),
    (r"\bpython\b", "Python"),
    (r"\bgolang\b|\bgo\b(?!\s+to)", "Go"),
    (r"\bruntime\b.*\brust\b|\brust\b(?:\s+lang)?", "Rust"),
    (r"\bjava\b(?!script)", "Java"),
    (r"\bc\+\+\b|\bcpp\b", "C++"),
    (r"\bc#\b|\bcsharp\b", "C#"),
    (r"\bkotlin\b", "Kotlin"),
    (r"\bswift\b", "Swift"),
    (r"\bruby\b", "Ruby"),
    (r"\bphp\b", "PHP"),
    (r"\bscala\b", "Scala"),
    (r"\belixir\b", "Elixir"),
    (r"\br\b(?:\s+programming|\s+language)", "R"),
    (r"\bmatlab\b", "MATLAB"),
    # Frontend frameworks
    (r"\breact\s+native\b", "React Native"),
    (r"\breact\.?js\b|\breact\b", "React"),
    (r"\bvue\.?js\b|\bvue\b", "Vue.js"),
    (r"\bangular\b", "Angular"),
    (r"\bsvelte\b", "Svelte"),
    (r"\bnext\.?js\b", "Next.js"),
    (r"\bnuxt\.?js\b", "Nuxt.js"),
    (r"\bwebpack\b", "Webpack"),
    (r"\bvite\b", "Vite"),
    (r"\btailwind\b", "Tailwind CSS"),
    (r"\bsass\b|\bscss\b", "Sass/SCSS"),
    # Backend frameworks
    (r"\bdjango\b", "Django"),
    (r"\bfastapi\b", "FastAPI"),
    (r"\bflask\b", "Flask"),
    (r"\blaravel\b", "Laravel"),
    (r"\brails\b|\bruby on rails\b", "Rails"),
    (r"\bspring\b(?:\s+boot)?", "Spring Boot"),
    (r"\bexpress\.?js\b|\bexpress\b", "Express"),
    (r"\bnode\.?js\b", "Node.js"),
    (r"\bnestjs\b|\bnest\.js\b", "NestJS"),
    (r"\bgin\b(?:\s+framework)?", "Gin"),
    # Mobile
    (r"\bflutter\b", "Flutter"),
    (r"\bxamarin\b", "Xamarin"),
    (r"\bios\b", "iOS"),
    (r"\bandroid\b", "Android"),
    # Databases
    (r"\bpostgresql\b|\bpostgres\b", "PostgreSQL"),
    (r"\bmysql\b", "MySQL"),
    (r"\bsqlite\b", "SQLite"),
    (r"\bmongodb\b|\bmongo\b", "MongoDB"),
    (r"\bredis\b", "Redis"),
    (r"\belasticsearch\b", "Elasticsearch"),
    (r"\bcassandra\b", "Cassandra"),
    (r"\bdynamodb\b", "DynamoDB"),
    (r"\bfirebase\b", "Firebase"),
    (r"\bsql\b", "SQL"),
    (r"\bnosql\b", "NoSQL"),
    # Cloud & DevOps
    (r"\bamazon web services\b|\baws\b", "AWS"),
    (r"\bgoogle cloud\b|\bgcp\b", "GCP"),
    (r"\bmicrosoft azure\b|\bazure\b", "Azure"),
    (r"\bkubernetes\b|\bk8s\b", "Kubernetes"),
    (r"\bdocker\b", "Docker"),
    (r"\bterraform\b", "Terraform"),
    (r"\bansible\b", "Ansible"),
    (r"\bhelm\b", "Helm"),
    (r"\bgithub actions\b", "GitHub Actions"),
    (r"\bgitlab ci\b", "GitLab CI"),
    (r"\bjenkins\b", "Jenkins"),
    (r"\bci/cd\b|\bcicd\b", "CI/CD"),
    (r"\bprometheus\b", "Prometheus"),
    (r"\bgrafana\b", "Grafana"),
    (r"\bnginx\b", "Nginx"),
    # ML / AI
    (r"\bpytorch\b", "PyTorch"),
    (r"\btensorflow\b", "TensorFlow"),
    (r"\bscikit.learn\b|\bsklearn\b", "scikit-learn"),
    (r"\bkeras\b", "Keras"),
    (r"\bhugging\s*face\b", "HuggingFace"),
    (r"\blangchain\b", "LangChain"),
    (r"\bopenai\b", "OpenAI"),
    (r"\bllm\b", "LLM"),
    (r"\brag\b", "RAG"),
    (r"\bnlp\b|\bnatural language processing\b", "NLP"),
    (r"\bcomputer vision\b", "Computer Vision"),
    (r"\bmlops\b", "MLOps"),
    (r"\bpandas\b", "Pandas"),
    (r"\bnumpy\b", "NumPy"),
    (r"\bjupyter\b", "Jupyter"),
    (r"\bspark\b", "Apache Spark"),
    (r"\bairflow\b", "Apache Airflow"),
    # Data & Analytics
    (r"\btableau\b", "Tableau"),
    (r"\bpower bi\b", "Power BI"),
    (r"\blooker\b", "Looker"),
    (r"\bdbt\b", "dbt"),
    (r"\bsnowflake\b", "Snowflake"),
    (r"\bbigquery\b", "BigQuery"),
    (r"\bredshift\b", "Redshift"),
    # Security
    (r"\bpenetration testing\b|\bpen test\b|\bpentest\b", "Penetration Testing"),
    (r"\bowasp\b", "OWASP"),
    (r"\bsoc\b(?:\s+analyst)?", "SOC"),
    (r"\bdevsecops\b", "DevSecOps"),
    (r"\bsiem\b", "SIEM"),
    # Design
    (r"\bfigma\b", "Figma"),
    (r"\badobe xd\b", "Adobe XD"),
    (r"\bsketch\b", "Sketch"),
    (r"\binvision\b", "InVision"),
    (r"\buser research\b", "User Research"),
    (r"\bprototyping\b", "Prototyping"),
    (r"\bwireframing\b", "Wireframing"),
    # Testing
    (r"\bselenium\b", "Selenium"),
    (r"\bcypress\b", "Cypress"),
    (r"\bplaywright\b", "Playwright"),
    (r"\bjest\b", "Jest"),
    (r"\bpytest\b", "Pytest"),
    (r"\bpostman\b", "Postman"),
    # Messaging / APIs
    (r"\bkafka\b", "Kafka"),
    (r"\brabbitmq\b", "RabbitMQ"),
    (r"\bgraphql\b", "GraphQL"),
    (r"\brest\s*api\b|\brestful\b", "REST API"),
    (r"\bgrpc\b", "gRPC"),
    (r"\bwebsocket\b", "WebSockets"),
    # Game dev
    (r"\bunity\b", "Unity"),
    (r"\bunreal\b(?:\s+engine)?", "Unreal Engine"),
    # Soft / process skills
    (r"\bagile\b", "Agile"),
    (r"\bscrum\b", "Scrum"),
    (r"\bkanban\b", "Kanban"),
    (r"\bjira\b", "Jira"),
    (r"\bconfluence\b", "Confluence"),
    (r"\bgit\b", "Git"),
    (r"\blinux\b", "Linux"),
    (r"\bbash\b|\bshell scripting\b", "Bash"),
    (r"\bmicroservices\b", "Microservices"),
    (r"\bsystem design\b", "System Design"),
    (r"\bapi design\b", "API Design"),
]


# Minimum skills assigned when regex + tags find nothing (e.g. jobspy empty descriptions).
# Based on the canonical field — keeps those jobs useful in the RAG.
FIELD_DEFAULT_SKILLS: dict[str, list[str]] = {
    "Frontend Development":   ["JavaScript", "HTML", "CSS", "React"],
    "Backend Development":    ["Python", "REST API", "SQL", "Node.js"],
    "Full Stack Development": ["JavaScript", "React", "Node.js", "SQL"],
    "Mobile Development":     ["iOS", "Android", "React Native", "Flutter"],
    "Data Analysis":          ["SQL", "Python", "Pandas", "Tableau"],
    "Data Science":           ["Python", "Machine Learning", "Pandas", "NumPy"],
    "Machine Learning":       ["Python", "Machine Learning", "PyTorch", "TensorFlow"],
    "AI Engineering":         ["Python", "LLM", "NLP", "OpenAI"],
    "Cyber Security":         ["Cyber Security", "Python", "Linux", "OWASP"],
    "DevOps":                 ["Docker", "Kubernetes", "AWS", "CI/CD"],
    "QA / Software Testing":  ["QA", "Test Automation", "Selenium", "Python"],
    "Game Development":       ["Unity", "C++", "C#", "Unreal Engine"],
    "UI / UX Design":         ["Figma", "UI/UX", "Prototyping", "User Research"],
    "Product Management":     ["Agile", "Scrum", "Jira", "Product Design"],
    "Technical Writing":      ["Technical Writing", "Markdown", "Git", "API Design"],
    "Software Architecture":  ["System Design", "Microservices", "REST API", "SQL"],
}


def load_aliases() -> dict[str, str]:
    with open(ALIASES_FILE) as f:
        return json.load(f)["aliases"]


def extract_skills_regex(text: str) -> list[str]:
    text_lower = text.lower()
    found: set[str] = set()
    for pattern, canonical in SKILL_PATTERNS:
        if re.search(pattern, text_lower):
            found.add(canonical)
    return sorted(found)


def extract_skills_llm(text: str, field: str) -> list[str]:
    """Use local Ollama to extract skills when regex misses nuance."""
    prompt = (
        f"Extract all technical skills, tools, programming languages, and frameworks "
        f"from this {field} job description. Return ONLY a JSON array of short skill names, "
        f"no explanation.\n\nJob description:\n{text[:1500]}\n\nSkills JSON array:"
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 200},
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        # Extract JSON array from response
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            skills = json.loads(match.group())
            return [str(s).strip() for s in skills if s]
    except Exception:
        pass
    return []


def normalize_skill(skill: str, aliases: dict[str, str]) -> str:
    return aliases.get(skill.lower(), skill)


def process_file(source_file: Path, use_llm: bool, aliases: dict[str, str]) -> None:
    print(f"\nProcessing {source_file.name}...")
    with open(source_file, encoding="utf-8") as f:
        jobs = json.load(f)

    updated = 0
    for job in jobs:
        if "skills" in job and not use_llm:
            continue

        text = f"{job.get('title', '')} {job.get('description', '')} {' '.join(job.get('tags', []))}"
        skills: set[str] = set()

        # Regex extraction (always)
        for s in extract_skills_regex(text):
            skills.add(normalize_skill(s, aliases))

        # Tag-based extraction: run each tag through SKILL_PATTERNS first so
        # raw tags like "react" become "React" rather than a lowercase duplicate.
        for tag in job.get("tags", []):
            tag_lower = tag.strip().lower()
            if not tag_lower or len(tag_lower) < 2:
                continue
            matched = False
            for pattern, canonical in SKILL_PATTERNS:
                if re.search(pattern, tag_lower):
                    skills.add(normalize_skill(canonical, aliases))
                    matched = True
                    break
            if not matched:
                canonical = normalize_skill(tag.strip(), aliases)
                if canonical and len(canonical) > 2:
                    skills.add(canonical)

        # LLM enrichment (optional, slow)
        if use_llm:
            llm_skills = extract_skills_llm(job.get("description", ""), job.get("field", ""))
            for s in llm_skills:
                skills.add(normalize_skill(s, aliases))
            time.sleep(0.5)

        # Fallback: if nothing found, assign field-based defaults so the job
        # still produces a meaningful RAG embedding
        if not skills:
            field = job.get("field", "")
            for s in FIELD_DEFAULT_SKILLS.get(field, []):
                skills.add(s)

        job["skills"] = sorted(skills)
        updated += 1

    with open(source_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"  Updated {updated} jobs with skills → {source_file}")

    # Quick summary
    all_skills: dict[str, int] = {}
    for job in jobs:
        for skill in job.get("skills", []):
            all_skills[skill] = all_skills.get(skill, 0) + 1
    top = sorted(all_skills.items(), key=lambda x: -x[1])[:10]
    print("  Top 10 skills:", ", ".join(f"{s}({c})" for s, c in top))


def main():
    parser = argparse.ArgumentParser(description="Extract skills from scraped job ads")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help="Which source files to process (default: all files in jobs/raw/)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enrich with Ollama LLM extraction (slower but more thorough)",
    )
    args = parser.parse_args()

    aliases = load_aliases()

    if args.sources is None:
        source_files = sorted(JOB_ADS_DIR.glob("*.json"))
    else:
        source_files = [JOB_ADS_DIR / f"{s}.json" for s in args.sources]

    for source_file in source_files:
        if not source_file.exists():
            print(f"  Skipping {source_file.name} — file not found. Run scrape_job_ads.py first.")
            continue
        process_file(source_file, args.use_llm, aliases)

    print("\nDone. Next step: run data/scripts/build_rag.py")


if __name__ == "__main__":
    main()
