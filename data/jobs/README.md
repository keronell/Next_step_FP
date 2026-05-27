# Jobs Data Pipeline

Three scripts build the job ads RAG store from scratch. Run them in order.

```
scrape_job_ads.py  →  extract_skills.py  →  build_rag.py
     ↓                      ↓                    ↓
 jobs/raw/*.json     adds `skills` list     jobs/chroma/
```

---

## 1. scrape_job_ads.py

Fetches job postings from four free APIs and saves them as JSON.

**Sources:**
- **RemoteOK** (`remoteok.com/api`) — single endpoint, returns all current remote jobs with tags
- **Jobicy** (`jobicy.com/api/v2/remote-jobs`) — paginated (up to 5 pages × 50 jobs)
- **Remotive** (`remotive.com/api/remote-jobs`) — fetched per-category (9 tech categories), highest volume
- **Arbeitnow** (`arbeitnow.com/api/job-board-api`) — paginated (up to 10 pages), remote-only filter applied

**Field matching — how it works:**
Every job is scored against the 16 canonical fields in `config/field_taxonomy.json`:
- Title keyword match → +3 points (e.g. "machine learning engineer" matches ML)
- Tag match → +2 points (e.g. tag "pytorch" matches ML)
- Job with highest score wins; jobs with score 0 are dropped

**Tag normalization (bug fix):** Tags are normalized before comparison — hyphens and dots are replaced with spaces. This fixes the core mismatch where the taxonomy stored `"machine-learning"` but APIs return `"machine learning"`.

For Remotive, some categories are unambiguous (e.g. `devops-sysadmin` → DevOps, `qa` → QA) and are assigned directly without scoring.

**Output:** `jobs/raw/remoteok.json`, `jobs/raw/jobicy.json`, `jobs/raw/remotive.json`, `jobs/raw/arbeitnow.json`
Each job has: `id`, `source`, `field`, `title`, `company`, `description`, `tags`, `url`, `date`

```bash
python data/scripts/scrape_job_ads.py
python data/scripts/scrape_job_ads.py --sources remotive arbeitnow
python data/scripts/scrape_job_ads.py --max-per-field 200
```

---

## 2. extract_skills.py

Reads the raw job JSONs and adds a normalized `skills` list to each job.

**Two extraction layers:**

1. **Regex patterns** (always runs) — 100+ patterns covering languages, frameworks, cloud tools, databases, design tools, testing tools. Each pattern maps to a canonical skill name (e.g. `\bk8s\b` → `"Kubernetes"`).

2. **Tag passthrough** — RemoteOK tags are often clean skill names already; these are normalized via `config/skill_aliases.json` (e.g. `"react.js"` → `"React"`) and added directly.

3. **LLM enrichment** (optional, `--use-llm`) — sends the job description to local Ollama and asks it to return a JSON array of skills. Slower but catches skills the regex misses.

**Output:** Updates `jobs/raw/*.json` in place — each job gains a `"skills": [...]` field.

```bash
python data/scripts/extract_skills.py
python data/scripts/extract_skills.py --use-llm          # richer but slow
python data/scripts/extract_skills.py --sources remoteok
```

---

## 3. build_rag.py

Embeds every job posting and stores it in a ChromaDB vector database.

**What it does:**
1. Loads all `jobs/raw/*.json` files
2. Builds a text document per job: `"Job: <title> | Field: <field> | Skills: <skills> | <description[:400]>"`
3. Embeds each document with `sentence-transformers/all-MiniLM-L6-v2` (384-dim vectors)
4. Upserts into ChromaDB collection `job_ads` with cosine similarity space
5. Stores metadata: `field`, `title`, `company`, `skills` (JSON string), `url`, `date`

**Why this structure:** The description is truncated to 400 chars to keep embeddings focused on the signal (title + skills) rather than boilerplate. Skills are stored as both part of the document text (for semantic search) and as metadata (for exact filtering).

**Querying the store** (used later by the roadmap generator):
- Given a user's selected field, retrieve the top-N most similar job postings
- Extract skill frequency across those postings → real market-driven requirements
- Compute gap between user skill vector and those requirements

```bash
python data/scripts/build_rag.py
python data/scripts/build_rag.py --reset                         # rebuild from scratch
python data/scripts/build_rag.py --stats-only                    # just print counts
python data/scripts/build_rag.py --query "React TypeScript" --field "Frontend Development"
```

---

## Folder contents

```
jobs/
  README.md           ← this file
  raw/
    remoteok.json     ← scraped from RemoteOK API
    jobicy.json       ← scraped from Jobicy API
    remotive.json     ← scraped from Remotive API (9 tech categories)
    arbeitnow.json    ← scraped from Arbeitnow API (remote-only)
  chroma/             ← ChromaDB persistent store (auto-created by build_rag.py)
```
