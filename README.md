# NextStep Career Matcher

A prototype career matching system that helps users discover their ideal tech career path through a personalized assessment and generates custom learning roadmaps.

---

## Local API (FastAPI + ChromaDB RAG matching)

> The backend for the live React SPA. It connects the questionnaire to the ChromaDB
> job-ad vector store (plus an optional Supabase/PostgreSQL layer) and returns
> explainable career recommendations.

### What it does

```
React questionnaire  →  POST /api/questionnaire/submit  →  FastAPI
  → build a natural-language profile from the answers
  → query the existing ChromaDB `job_ads` store (per career field)
  → blend semantic similarity + questionnaire fit + skill overlap into a score
  → return top-3 sorted, explainable recommendations  →  rendered in the SPA
```

The 6 careers (frontend, backend, data-science, devops, product-manager,
ux-designer) and their roadmaps are unchanged; each is enriched with RAG signals.

### Prerequisites

- Python 3.12 (a venv already exists at `backend/venv`)
- Node 18+ for the frontend
- The ChromaDB store built from the scraped job ads (step 2 below)

### 1. Install backend dependencies

```bash
backend/venv/bin/python -m pip install -r backend/requirements.txt
```

### 2. Build the ChromaDB store (one-time, uses the existing ingestion pipeline)

```bash
backend/venv/bin/python data/scripts/build_rag.py
```

This embeds ~1575 job ads with `all-MiniLM-L6-v2` into `data/jobs/chroma/`
(collection `job_ads`, cosine space). It is the existing pipeline — not re-written.

### 3. Run the API

```bash
cd backend
venv/bin/python -m uvicorn app.main:app --port 8000
# (optional) copy backend/.env.example -> backend/.env to override defaults
```

Startup logs report the loaded collection size. If the store is missing the API
still starts and serves `/api/health`; `/submit` then returns a safe 503 and the
frontend falls back to an offline estimate.

### 4. Run the frontend against it

```bash
cd frontend
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm install            # first time only
npm run dev            # http://localhost:3000
```

### Example request / response

```bash
curl -s -X POST http://localhost:8000/api/questionnaire/submit \
  -H 'Content-Type: application/json' \
  -d '{"answers":{"q1":3,"q2":2,"q3":3,"q4":2,"q5":2,"q6":2,"q7":2,"q8":2,"q9":1,"q10":2}}'
```

```json
{
  "request_id": "…",
  "recommendations": [
    {
      "id": "data-science", "title": "Data Scientist", "description": "…",
      "keySkills": ["Python","Statistics","Machine Learning","SQL","Data Viz"],
      "icon": "BarChart2", "roadmapKey": "data-science",
      "matchPercent": 66, "score": 0.66,
      "score_breakdown": {"semantic_similarity": 0.31, "questionnaire_fit": 0.75, "skill_overlap": 0.8},
      "reasons": ["Strong alignment with your interests and work style",
                  "Builds on in-demand skills like Python, Statistics, Machine Learning"],
      "matched_skills": ["Python","Statistics","Machine Learning","SQL"],
      "missing_skills": ["R","Data Visualization","Excel","Hadoop"]
    }
  ]
}
```

### Matching formula

```
final = 0.40 * questionnaire_fit + 0.40 * semantic_similarity + 0.20 * skill_overlap
```

- `questionnaire_fit` — ported WEIGHTS+BONUSES from `frontend/src/data.js`, normalized
  relative to the strongest-fitting career.
- `semantic_similarity` — ChromaDB cosine distance converted to `1 - distance`.
- `skill_overlap` — share of a career's key skills present in the retrieved job ads.

Weights live in one place (`backend/app/services/matching_service.py`) and are
asserted to sum to 1. Missing data never earns a component. See that file for the
full documented assumptions.

### Run tests

```bash
cd backend
venv/bin/python -m pytest app/tests -q
```

The tests mock the vector store via a fake repository, so they run without
ChromaDB or the embedding model.

### Environment variables

| Variable | Where | Default | Purpose |
|----------|-------|---------|---------|
| `CHROMA_PATH` | backend | `data/jobs/chroma` | ChromaDB persistence path |
| `CHROMA_COLLECTION` | backend | `job_ads` | Collection name |
| `EMBED_MODEL` | backend | `all-MiniLM-L6-v2` | Must match the store's model |
| `RAG_TOP_K` | backend | `8` | Job ads retrieved per career field |
| `CORS_ORIGINS` | backend | `http://localhost:3000` | Allowed frontend origins |
| `API_PORT` / `LOG_LEVEL` | backend | `8000` / `INFO` | Server config |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | backend | _(empty)_ | Enable Postgres persistence + `job_postings` reads (server-only service_role key) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | backend | _(empty)_ / `gpt-4o-mini` | Enable LLM roadmap generation (falls back to static when unset) |
| `VITE_API_BASE_URL` | frontend | `http://localhost:8000` | Backend base URL |

### Persistence & roadmap generation (optional)

All external services are optional — with an empty `.env` the app runs on ChromaDB-only
matching and static roadmaps.

- **Submissions** (`request_id`, answers, recommendations, `session_id`, `selected_career`) are
  saved to the Supabase `submissions` table as a best-effort background task. The frontend mints
  an anonymous `session_id` (localStorage) and `POST /api/questionnaire/select` records the chosen
  career. No-op when `SUPABASE_*` is unset.
- **Job postings** scraped into `data/jobs/raw/*.json` are upserted into the Supabase
  `job_postings` table by `data/scripts/build_rag.py` (flow: scrape → JSON → Postgres → ChromaDB);
  their skills reinforce the matcher's skill-overlap signal.
- **Roadmaps:** `GET /api/roadmap/{id}` returns the curated static roadmap; `POST /api/roadmap/{id}`
  generates a personalized one via OpenAI (when `OPENAI_API_KEY` is set) and **falls back to the
  static data on any failure**.

### Deployment

Terminate TLS at a reverse proxy (nginx / Caddy / cloud load balancer) — the FastAPI app runs
plain HTTP behind it and needs no TLS config. Point `CORS_ORIGINS` and `VITE_API_BASE_URL` at the
public HTTPS origins, and run uvicorn with `--proxy-headers`.

---

## Tech stack

**Backend:** FastAPI, ChromaDB (vector store), sentence-transformers (`all-MiniLM-L6-v2`),
Supabase/PostgreSQL (persistence + job postings), OpenAI (roadmap generation), pytest.

**Frontend:** React 18, Vite, Tailwind CSS, framer-motion, lucide-react.

**Data pipeline:** `data/scripts/` — job-ad scrapers (httpx / RSS / jobspy), skill extraction, RAG builder.

## Project structure

```
Next_step_FP/
├── backend/
│   ├── app/                     # live FastAPI app (the one the SPA calls)
│   │   ├── api/routes/          # health, questionnaire, roadmap
│   │   ├── services/            # profile, rag_service, matching_service, roadmap_service,
│   │   │                        #   job_postings_service, supabase_client, persistence
│   │   ├── repositories/        # career_repository (catalog + RAG + Postgres skills)
│   │   ├── models/  data/  tests/
│   │   └── main.py
│   ├── migrations/              # SQL (job_postings)
│   └── requirements.txt
├── frontend/
│   └── src/                     # App.jsx (single-page SPA), api.js, data.js, pages/, components/
├── data/
│   ├── scripts/                 # scrape_job_ads.py, extract_skills.py, build_rag.py
│   └── jobs/                    # raw/*.json + chroma/ (gitignored)
└── README.md
```

## License

MIT

