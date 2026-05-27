"""
Job ads scraper — RemoteOK, Jobicy, Remotive, Arbeitnow, Working Nomads,
                  We Work Remotely (RSS), python-jobspy (LinkedIn + Indeed).
Saves raw JSON per source to data/jobs/raw/.

Usage:
    python data/scripts/scrape_job_ads.py
    python data/scripts/scrape_job_ads.py --sources jobspy workingnomads weworkremotely
    python data/scripts/scrape_job_ads.py --max-per-field 200
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

CONFIG_DIR = Path("data/config")
OUTPUT_DIR = Path("data/jobs/raw")
TAXONOMY_FILE = CONFIG_DIR / "field_taxonomy.json"

REMOTEOK_URL = "https://remoteok.com/api"
JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
WORKINGNOMADS_URL = "https://www.workingnomads.com/api/exposed_jobs/"
WWR_RSS_BASE = "https://weworkremotely.com/categories/remote-{slug}-jobs.rss"
THEMUSE_URL = "https://www.themuse.com/api/public/jobs"

# Working Nomads category slugs → canonical field override (None = use scoring)
WORKINGNOMADS_CATEGORIES = [
    ("development",     None),
    ("devops-sysadmin", "DevOps"),
    ("design",          "UI / UX Design"),
    ("product",         "Product Management"),
    ("writing",         "Technical Writing"),
    ("security",        "Cyber Security"),
    ("mobile",          "Mobile Development"),
    ("qa",              "QA / Software Testing"),
]

# We Work Remotely RSS slugs → canonical field override (None = use scoring)
WWR_CATEGORIES = [
    ("programming",     None),
    ("devops-sysadmin", "DevOps"),
    ("design",          "UI / UX Design"),
    ("product",         "Product Management"),
    ("copywriting",     "Technical Writing"),
    ("security",        "Cyber Security"),
]

# jobspy: search terms per canonical field (LinkedIn/Indeed).
# Simpler single-concept queries work better — complex strings get zero results.
JOBSPY_SEARCHES: list[tuple[str, str]] = [
    # AI Engineering — 3 passes, simple terms
    ("AI Engineering",         "AI engineer"),
    ("AI Engineering",         "LLM engineer generative AI"),
    ("AI Engineering",         "NLP engineer machine learning AI"),
    # Software Architecture — 3 passes
    ("Software Architecture",  "software architect"),
    ("Software Architecture",  "solutions architect cloud"),
    ("Software Architecture",  "principal engineer staff engineer"),
    # Frontend — 2 passes
    ("Frontend Development",   "frontend developer React TypeScript"),
    ("Frontend Development",   "Vue Angular JavaScript frontend"),
    # Backend — 2 passes
    ("Backend Development",    "backend developer Python API"),
    ("Backend Development",    "backend engineer Node Java Golang"),
    # Full Stack — 2 passes
    ("Full Stack Development", "full stack developer React Node"),
    ("Full Stack Development", "fullstack JavaScript TypeScript"),
    # Mobile — 2 passes
    ("Mobile Development",     "mobile developer iOS Android"),
    ("Mobile Development",     "React Native Flutter Kotlin Swift"),
    # Remaining fields — single pass each
    ("Data Analysis",          "data analyst SQL business intelligence"),
    ("Data Science",           "data scientist statistics Python"),
    ("Machine Learning",       "machine learning engineer PyTorch TensorFlow"),
    ("Cyber Security",         "cybersecurity engineer security analyst"),
    ("DevOps",                 "devops engineer Kubernetes AWS Terraform"),
    ("QA / Software Testing",  "QA engineer test automation SDET"),
    ("Game Development",       "game developer Unity Unreal"),
    ("UI / UX Design",         "UX designer product designer Figma"),
    ("Product Management",     "product manager technical PM"),
    ("Technical Writing",      "technical writer developer documentation"),
]

HEADERS = {
    "User-Agent": "NextStep-Career-Matcher/1.0 (research project)",
    "Accept": "application/json",
}

REQUEST_DELAY = 2.0  # seconds between requests

# The Muse — free public API, no auth required
THEMUSE_CATEGORIES = [
    ("Engineering", None),
    ("Data Science", None),
    ("Design", "UI / UX Design"),
    ("Product", "Product Management"),
]

# Remotive has per-category endpoints. field_override=None means use title/tag matching.
REMOTIVE_CATEGORIES = [
    ("software-dev",    None),
    ("devops-sysadmin", "DevOps"),
    ("design",          "UI / UX Design"),
    ("data",            None),
    ("product",         "Product Management"),
    ("writing",         "Technical Writing"),
    ("qa",              "QA / Software Testing"),
    ("security",        "Cyber Security"),
    ("mobile",          "Mobile Development"),
]


def load_taxonomy() -> dict:
    with open(TAXONOMY_FILE) as f:
        return json.load(f)


def _normalize_tag(tag: str) -> str:
    """Lowercase and replace hyphens/dots with spaces for comparison.

    Fixes the core matching bug: taxonomy stores "machine-learning" but
    RemoteOK returns "machine learning" — without this they never match.
    """
    return re.sub(r"[-.]", " ", tag.lower()).strip()


def _score_fields(title: str, tags: list[str], taxonomy: dict) -> tuple[str | None, int]:
    """Return (best_canonical_field, score) from title and tag signals."""
    normalized_tags = {_normalize_tag(t) for t in tags}
    title_lower = title.lower()
    best_field = None
    best_score = 0

    for field in taxonomy["fields"]:
        score = 0
        for tag in field["remoteok_tags"]:
            if _normalize_tag(tag) in normalized_tags:
                score += 2
        for kw in field["title_keywords"]:
            if kw.lower() in title_lower:
                score += 3
        if score >= best_score and score > 0:
            best_score = score
            best_field = field["canonical"]

    return best_field, best_score


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return re.sub(r"\s+", " ", text).strip()


def _apply_cap_and_report(jobs: list[dict], max_per_field: int) -> list[dict]:
    field_counts: dict[str, int] = {}
    results = []
    for job in jobs:
        field = job.get("field")
        if not field:
            continue
        if field_counts.get(field, 0) >= max_per_field:
            continue
        field_counts[field] = field_counts.get(field, 0) + 1
        results.append(job)
    print(f"  Kept {len(results)} jobs across {len(field_counts)} fields")
    for f, c in sorted(field_counts.items()):
        print(f"    {f}: {c}")
    return results


# ── scrapers ────────────────────────────────────────────────────────────────

def scrape_remoteok(taxonomy: dict, max_per_field: int) -> list[dict]:
    print("Fetching RemoteOK...")
    time.sleep(REQUEST_DELAY)
    try:
        resp = httpx.get(REMOTEOK_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  Failed: {e}")
        return []

    raw = [j for j in resp.json() if isinstance(j, dict) and "id" in j]
    print(f"  Got {len(raw)} raw jobs")

    normalized = []
    for job in raw:
        field, _ = _score_fields(job.get("position", ""), job.get("tags", []), taxonomy)
        if not field:
            continue
        normalized.append({
            "id": f"remoteok_{job['id']}",
            "source": "remoteok",
            "field": field,
            "title": job.get("position", ""),
            "company": job.get("company", ""),
            "description": _strip_html(job.get("description", "")),
            "tags": job.get("tags", []),
            "url": job.get("url", ""),
            "date": job.get("date", ""),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })

    return _apply_cap_and_report(normalized, max_per_field)


def scrape_jobicy(taxonomy: dict, max_per_field: int) -> list[dict]:
    """Jobicy v2 API does not support pagination.
    Workaround: fetch once per tech tag to get broader coverage."""
    print("Fetching Jobicy...")

    # Tags that map well to underrepresented canonical fields
    JOBICY_TAGS = [
        "javascript", "typescript", "react", "python", "node",
        "devops", "aws", "kubernetes", "golang", "rust",
        "machine-learning", "data-science", "ai", "llm",
        "ios", "android", "flutter",
        "qa", "testing", "security",
        "fullstack", "backend", "frontend",
    ]

    seen_ids: set[str] = set()
    all_raw = []

    # Fetch unfiltered first (latest 50 jobs)
    time.sleep(REQUEST_DELAY)
    try:
        resp = httpx.get(JOBICY_URL, headers=HEADERS, params={"count": 50}, timeout=30)
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])
        all_raw.extend(jobs)
        seen_ids.update(str(j.get("id", "")) for j in jobs)
        print(f"  unfiltered: {len(jobs)} jobs")
    except httpx.HTTPError as e:
        print(f"  unfiltered fetch failed: {e}")

    # Fetch per tag
    for tag in JOBICY_TAGS:
        time.sleep(REQUEST_DELAY)
        try:
            resp = httpx.get(JOBICY_URL, headers=HEADERS, params={"count": 50, "tag": tag}, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  tag={tag} failed: {e}")
            continue
        jobs = resp.json().get("jobs", [])
        new = [j for j in jobs if str(j.get("id", "")) not in seen_ids]
        seen_ids.update(str(j.get("id", "")) for j in new)
        all_raw.extend(new)
        print(f"  tag={tag}: {len(jobs)} jobs ({len(new)} new)")

    print(f"  Got {len(all_raw)} raw jobs")

    normalized = []
    for job in all_raw:
        # Pass jobCategory words as extra tags to improve scoring
        category_words = re.split(r"[\s,/&]+", job.get("jobCategory", "").lower())
        all_tags = list(job.get("jobTags", [])) + category_words
        field, _ = _score_fields(job.get("jobTitle", ""), all_tags, taxonomy)
        if not field:
            continue
        normalized.append({
            "id": f"jobicy_{job.get('id', '')}",
            "source": "jobicy",
            "field": field,
            "title": job.get("jobTitle", ""),
            "company": job.get("companyName", ""),
            "description": _strip_html(job.get("jobDescription", "")),
            "tags": job.get("jobTags", []),
            "url": job.get("url", ""),
            "date": job.get("pubDate", ""),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })

    return _apply_cap_and_report(normalized, max_per_field)


def scrape_remotive(taxonomy: dict, max_per_field: int) -> list[dict]:
    print("Fetching Remotive...")
    normalized = []

    for category_slug, field_override in REMOTIVE_CATEGORIES:
        time.sleep(REQUEST_DELAY)
        try:
            resp = httpx.get(
                REMOTIVE_URL,
                headers=HEADERS,
                params={"category": category_slug, "limit": 100},
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  {category_slug} failed: {e}")
            continue

        jobs = resp.json().get("jobs", [])
        print(f"  {category_slug}: {len(jobs)} jobs")

        for job in jobs:
            if field_override:
                field = field_override
            else:
                field, _ = _score_fields(job.get("title", ""), job.get("tags", []), taxonomy)
                if not field:
                    continue
            normalized.append({
                "id": f"remotive_{job.get('id', '')}",
                "source": "remotive",
                "field": field,
                "title": job.get("title", ""),
                "company": job.get("company_name", ""),
                "description": _strip_html(job.get("description", "")),
                "tags": job.get("tags", []),
                "url": job.get("url", ""),
                "date": job.get("publication_date", ""),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

    print(f"  Got {len(normalized)} total Remotive jobs")
    return _apply_cap_and_report(normalized, max_per_field)


def scrape_arbeitnow(taxonomy: dict, max_per_field: int) -> list[dict]:
    print("Fetching Arbeitnow...")
    all_raw = []
    for page in range(1, 11):
        time.sleep(REQUEST_DELAY)
        try:
            resp = httpx.get(ARBEITNOW_URL, headers=HEADERS, params={"page": page}, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  Page {page} failed: {e}")
            break
        jobs = resp.json().get("data", [])
        if not jobs:
            break
        remote = [j for j in jobs if j.get("remote")]
        all_raw.extend(remote)
        print(f"  Page {page}: {len(remote)} remote jobs (of {len(jobs)} total)")

    print(f"  Got {len(all_raw)} raw remote jobs")

    normalized = []
    for job in all_raw:
        field, _ = _score_fields(job.get("title", ""), job.get("tags", []), taxonomy)
        if not field:
            continue
        normalized.append({
            "id": f"arbeitnow_{job.get('slug', '')}",
            "source": "arbeitnow",
            "field": field,
            "title": job.get("title", ""),
            "company": job.get("company_name", ""),
            "description": _strip_html(job.get("description", "")),
            "tags": job.get("tags", []),
            "url": job.get("url", ""),
            "date": str(job.get("created_at", "")),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })

    return _apply_cap_and_report(normalized, max_per_field)


# ── new sources ─────────────────────────────────────────────────────────────

def _workingnomads_normalize(raw_jobs: list, field_override: str | None, seen_ids: set, taxonomy: dict) -> list[dict]:
    out = []
    for job in raw_jobs:
        job_id = str(job.get("id", job.get("slug", "")))
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        if field_override:
            field = field_override
        else:
            tags = re.split(r"[\s,]+", job.get("category", "").lower())
            field, _ = _score_fields(job.get("title", ""), tags, taxonomy)
            if not field:
                continue

        out.append({
            "id": f"workingnomads_{job_id}",
            "source": "workingnomads",
            "field": field,
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "description": _strip_html(job.get("description", job.get("body", ""))),
            "tags": re.split(r"[\s,]+", job.get("category", "")),
            "url": job.get("url", job.get("job_url", "")),
            "date": job.get("pub_date", job.get("created_at", "")),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


def scrape_workingnomads(taxonomy: dict, max_per_field: int) -> list[dict]:
    print("Fetching Working Nomads...")
    normalized = []
    seen_ids: set[str] = set()

    # Try unfiltered base fetch first — the per-category param may be silently empty
    time.sleep(REQUEST_DELAY)
    try:
        resp = httpx.get(WORKINGNOMADS_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
        base_jobs = raw if isinstance(raw, list) else raw.get("jobs", raw.get("data", []))
        print(f"  Base (all): {len(base_jobs)} jobs")
        normalized.extend(_workingnomads_normalize(base_jobs, None, seen_ids, taxonomy))
    except Exception as e:
        print(f"  Base fetch failed: {e}")

    # Per-category passes to catch jobs missed above
    for category_slug, field_override in WORKINGNOMADS_CATEGORIES:
        time.sleep(REQUEST_DELAY)
        try:
            resp = httpx.get(
                WORKINGNOMADS_URL,
                headers=HEADERS,
                params={"category": category_slug},
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()
            jobs = raw if isinstance(raw, list) else raw.get("jobs", raw.get("data", []))
            new = _workingnomads_normalize(jobs, field_override, seen_ids, taxonomy)
            normalized.extend(new)
            print(f"  {category_slug}: {len(jobs)} jobs ({len(new)} new)")
        except Exception as e:
            print(f"  {category_slug} failed: {e}")

    print(f"  Got {len(normalized)} total Working Nomads jobs")
    return _apply_cap_and_report(normalized, max_per_field)


def scrape_weworkremotely(taxonomy: dict, max_per_field: int) -> list[dict]:
    print("Fetching We Work Remotely (RSS)...")
    try:
        import feedparser
    except ImportError:
        print("  feedparser not installed — run: pip install feedparser")
        return []

    normalized = []
    seen_urls: set[str] = set()

    for slug, field_override in WWR_CATEGORIES:
        time.sleep(REQUEST_DELAY)
        url = WWR_RSS_BASE.format(slug=slug)
        feed = feedparser.parse(url)
        new_count = 0

        for entry in feed.entries:
            entry_url = entry.get("link", "")
            if entry_url in seen_urls:
                continue
            seen_urls.add(entry_url)

            title = entry.get("title", "")
            # WWR title format: "Company: Job Title"
            if ": " in title:
                company, title = title.split(": ", 1)
            else:
                company = ""

            description = _strip_html(entry.get("summary", ""))
            tags = [t.get("term", "") for t in entry.get("tags", [])]

            if field_override:
                field = field_override
            else:
                field, _ = _score_fields(title, tags, taxonomy)
                if not field:
                    continue

            job_id = re.sub(r"[^a-z0-9]", "_", entry_url.lower())[-60:]
            normalized.append({
                "id": f"wwr_{job_id}",
                "source": "weworkremotely",
                "field": field,
                "title": title,
                "company": company,
                "description": description,
                "tags": tags,
                "url": entry_url,
                "date": entry.get("published", ""),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
            new_count += 1

        print(f"  {slug}: {len(feed.entries)} entries ({new_count} new)")

    print(f"  Got {len(normalized)} total We Work Remotely jobs")
    return _apply_cap_and_report(normalized, max_per_field)


def scrape_jobspy(taxonomy: dict, max_per_field: int) -> list[dict]:
    """Search LinkedIn + Indeed per canonical field via python-jobspy."""
    print("Fetching via jobspy (LinkedIn + Indeed)...")
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("  python-jobspy not installed — run: pip install python-jobspy")
        return []

    normalized = []
    seen_urls: set[str] = set()

    for field, search_term in JOBSPY_SEARCHES:
        time.sleep(REQUEST_DELAY * 2)  # jobspy hits real sites — be polite
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=f"{search_term} remote",
                country_indeed="worldwide",
                results_wanted=100,  # was 40
                hours_old=720,       # 4 weeks, was 2 weeks
                verbose=0,
            )
        except Exception as e:
            print(f"  '{field}' / '{search_term}' failed: {e}")
            continue

        if df is None or df.empty:
            print(f"  '{field}': 0 results")
            continue

        new_count = 0
        for _, row in df.iterrows():
            url = str(row.get("job_url", ""))
            if url in seen_urls:
                continue
            seen_urls.add(url)

            job_id = re.sub(r"[^a-z0-9]", "_", url.lower())[-60:]
            tags = []
            if row.get("job_type"):
                tags.append(str(row["job_type"]))

            normalized.append({
                "id": f"jobspy_{job_id}",
                "source": "jobspy",
                "field": field,
                "title": str(row.get("title", "")),
                "company": str(row.get("company", "")),
                "description": _strip_html(str(row.get("description", "") or "")),
                "tags": tags,
                "url": url,
                "date": str(row.get("date_posted", "")),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
            new_count += 1

        print(f"  '{field}': {len(df)} results ({new_count} new)")

    print(f"  Got {len(normalized)} total jobspy jobs")
    return _apply_cap_and_report(normalized, max_per_field)


def scrape_themuse(taxonomy: dict, max_per_field: int) -> list[dict]:
    """The Muse public API — free, no auth, good AI/ML and engineering coverage.
    Returns 20 jobs per page; paginates until empty or cap reached."""
    print("Fetching The Muse...")
    normalized = []
    seen_ids: set[str] = set()

    for category, field_override in THEMUSE_CATEGORIES:
        for page in range(0, 50):  # 0-indexed; 50 pages × 20 = 1000 per category max
            time.sleep(REQUEST_DELAY)
            try:
                resp = httpx.get(
                    THEMUSE_URL,
                    headers={**HEADERS, "Accept": "application/json"},
                    params={"category": category, "page": page, "descending": "true"},
                    timeout=30,
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"  {category} page {page} failed: {e}")
                break

            data = resp.json()
            jobs = data.get("results", [])
            if not jobs:
                break

            new_count = 0
            for job in jobs:
                job_id = str(job.get("id", ""))
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                title = job.get("name", "")
                description = _strip_html(job.get("contents", ""))
                tags = [cat.get("name", "") for cat in job.get("categories", [])]
                company = (job.get("company") or {}).get("name", "")

                if field_override:
                    field = field_override
                else:
                    field, _ = _score_fields(title, tags, taxonomy)
                    if not field:
                        continue

                normalized.append({
                    "id": f"themuse_{job_id}",
                    "source": "themuse",
                    "field": field,
                    "title": title,
                    "company": company,
                    "description": description,
                    "tags": tags,
                    "url": (job.get("refs") or {}).get("landing_page", ""),
                    "date": job.get("publication_date", ""),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                })
                new_count += 1

            print(f"  {category} page {page}: {len(jobs)} results ({new_count} new)")
            if len(jobs) < 20:
                break  # last page

    print(f"  Got {len(normalized)} total The Muse jobs")
    return _apply_cap_and_report(normalized, max_per_field)


# ── shared helpers ───────────────────────────────────────────────────────────

def deduplicate(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique = []
    for job in jobs:
        key = f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def save_results(jobs: list[dict], source: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"{source}.json"

    existing = []
    if out_file.exists():
        with open(out_file, encoding="utf-8") as f:
            existing = json.load(f)
        existing_ids = {j["id"] for j in existing}
        new_jobs = [j for j in jobs if j["id"] not in existing_ids]
        jobs = existing + new_jobs
        print(f"  Merged {len(new_jobs)} new into {len(existing)} existing ({source})")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(jobs)} jobs → {out_file}")


# ── entry point ──────────────────────────────────────────────────────────────

CANONICAL_FIELDS = [
    "Frontend Development", "Backend Development", "Full Stack Development",
    "Mobile Development", "Data Analysis", "Data Science", "Machine Learning",
    "AI Engineering", "Cyber Security", "DevOps", "QA / Software Testing",
    "Game Development", "UI / UX Design", "Product Management",
    "Technical Writing", "Software Architecture",
]


def coverage_report(min_per_field: int = 50) -> None:
    """Print per-field job counts across all raw JSON files."""
    field_counts: dict[str, int] = {}
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            jobs = json.load(open(f, encoding="utf-8"))
            for j in jobs:
                field = j.get("field", "")
                if field:
                    field_counts[field] = field_counts.get(field, 0) + 1
        except Exception:
            pass

    total = sum(field_counts.values())
    print(f"\n{'='*60}")
    print(f"Coverage report  (total: {total} jobs, target: 500/field)")
    print(f"{'='*60}")
    for field in CANONICAL_FIELDS:
        cnt = field_counts.get(field, 0)
        status = "OK" if cnt >= min_per_field else "LOW"
        bar = "#" * min(cnt // 10, 40)
        print(f"  {'[' + status + ']':<6} {field:<30} {cnt:>4}  {bar}")
    missing = [f for f in CANONICAL_FIELDS if field_counts.get(f, 0) < min_per_field]
    if missing:
        print(f"\n  Fields below {min_per_field}: {', '.join(missing)}")
        print("  Tip: run with --sources jobspy themuse --fields <field> to target them")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Scrape job ads from free APIs")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["remoteok", "jobicy", "remotive", "arbeitnow", "workingnomads",
                 "weworkremotely", "jobspy", "themuse"],
        default=["remoteok", "jobicy", "remotive", "arbeitnow", "workingnomads",
                 "weworkremotely", "jobspy", "themuse"],
        help="Which sources to scrape (default: all)",
    )
    parser.add_argument(
        "--max-per-field",
        type=int,
        default=300,
        help="Max jobs per canonical field per source (default: 300)",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        metavar="FIELD",
        help="Only keep jobs for these canonical fields (e.g. 'AI Engineering'). "
             "Useful for targeted top-up runs.",
    )
    args = parser.parse_args()

    taxonomy = load_taxonomy()
    scrapers = {
        "remoteok":       scrape_remoteok,
        "jobicy":         scrape_jobicy,
        "remotive":       scrape_remotive,
        "arbeitnow":      scrape_arbeitnow,
        "workingnomads":  scrape_workingnomads,
        "weworkremotely": scrape_weworkremotely,
        "jobspy":         scrape_jobspy,
        "themuse":        scrape_themuse,
    }

    target_fields = set(args.fields) if args.fields else None

    total = 0
    for source in args.sources:
        jobs = scrapers[source](taxonomy, args.max_per_field)
        if target_fields:
            jobs = [j for j in jobs if j.get("field") in target_fields]
        jobs = deduplicate(jobs)
        save_results(jobs, source)
        total += len(jobs)
        print()

    print(f"Done. Total jobs saved this run: {total}")
    coverage_report()
    print("Next step: python data/scripts/extract_skills.py")


if __name__ == "__main__":
    main()
