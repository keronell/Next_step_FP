# NextStep Career Matcher

A career-discovery platform: a personalized assessment matches users to one of
**16 tech careers** with explainable, job-market-backed recommendations, then
generates a personal learning roadmap enriched with the skills employers
actually ask for.

The backend is **five microservices glued by [Dapr](https://dapr.io)** (service
invocation, pub/sub, state store) behind an nginx API gateway; the frontend is a
single-page React app that works even when the backend is down (offline
fallback). Full architecture: [`docs/architecture.md`](docs/architecture.md) ·
Dapr building blocks & state schema: [`docs/dapr.md`](docs/dapr.md).

```
React SPA (:3000)
   │
   ▼
nginx gateway (:8000)
   ├── questionnaire ── Dapr invoke ──▶ matching   (ChromaDB job-ad RAG + scoring)
   │        └── Dapr pub/sub (Redis) ──▶ history   (submissions in the Dapr state store)
   ├── roadmap  ── invoke ─▶ matching (market skills)  +  OpenAI (optional)
   └── auth     (Supabase GoTrue + usernames; other services verify via invoke)

infra: redis (state + broker) · consul (sidecar discovery) · 5 daprd sidecars
```

How a submission flows:

```
questionnaire answers → POST /api/questionnaire/submit
  → matching-service builds a natural-language profile from the answers
  → queries the ChromaDB `job_ads` store (~1575 scraped ads, per career field)
  → blends semantic similarity + questionnaire fit + skill overlap into a score
  → top-3 explainable recommendations return to the SPA
  → the submission is published to Redis and persisted by history-service
```

## Quick start

Prerequisites: **Docker Desktop**, **Node 18+**, **Python 3.12**
(a venv at `backend/venv`, rebuildable from `backend/requirements.txt`).

```bash
# 0. one-time: build the job-ad vector store (~1575 ads, all-MiniLM-L6-v2)
backend/venv/bin/python data/scripts/build_rag.py

# 1. secrets
cp .env.example .env            # set APP_API_TOKEN (openssl rand -hex 16)
cp backend/.env.example backend/.env   # optional: SUPABASE_* (auth), OPENAI_API_KEY (LLM roadmaps)

# 2. everything at once (compose stack + Vite + browser):
./dev.sh                        # Windows: powershell -ExecutionPolicy Bypass -File dev.ps1

# — or manually —
docker compose up -d --build    # 13 containers; gateway on :8000
cd frontend && npm install && npm run dev   # SPA on :3000
```

All external services are optional: without Supabase, auth routes return 503
(the questionnaire still works anonymously); without OpenAI, roadmaps fall back
to curated static data; without the ChromaDB store, matching returns a safe 503
and the SPA shows its offline estimate.

Sidecars share their app's network namespace — restart pairs together:
`docker compose restart matching matching-dapr`.

## Public API (through the gateway)

| Route | Service | Purpose |
|---|---|---|
| `GET /api/questions` | questionnaire | adaptive question bank |
| `POST /api/questionnaire/submit` | questionnaire | answers → recommendations |
| `POST /api/questionnaire/select` | questionnaire | record the chosen career |
| `GET /api/health` | matching | RAG store status (`rag_doc_count`) |
| `GET/POST /api/roadmap/{id}` | roadmap | static / personalized roadmap + in-demand market skills |
| `GET/POST /api/roadmap/{id}/progress` | roadmap | per-user completed nodes (auth) |
| `POST /api/auth/register\|login\|logout`, `GET /api/auth/me` | auth | Supabase GoTrue + usernames |
| `POST /api/auth/claim-sessions`, `GET /api/auth/my-submissions` | history | link anonymous submissions, submission history (auth) |

`/internal/*` (service-to-service), `/events/*` and `/dapr/*` (sidecar surface)
are deliberately not routed by the gateway.

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
      "missing_skills": ["R","Data Visualization","Excel","Hadoop"],
      "model_version": "formula-v1"
    }
  ]
}
```

### Matching formula

```
final = 0.40 * questionnaire_fit + 0.40 * semantic_similarity + 0.20 * skill_overlap
```

- `questionnaire_fit` — per-career answer weights + bonuses, normalized against
  the strongest-fitting career.
- `semantic_similarity` — ChromaDB cosine distance converted to `1 - distance`.
- `skill_overlap` — share of a career's key skills present in the retrieved ads.

Weights live in `services/matching/app/services/matching_service.py`, asserted
to sum to 1. An optional learned (logistic-regression) matcher can replace the
formula via `MATCHER_MODEL_PATH` — training pipeline under `data/scripts/`.

## Tests

Each service has an isolated suite (161 tests total) — external calls are faked
at seams, so no Docker, sidecar, or database is needed:

```bash
cd services/<questionnaire|matching|roadmap|auth|history>
../../backend/venv/bin/python -m pytest tests -q
```

## Environment variables

Two scopes (they do not overlap):

| Scope | File | Keys |
|---|---|---|
| docker-compose interpolation | repo-root `.env` | `APP_API_TOKEN` — **required**; gates history-service's event-ingestion endpoints |
| services (via `env_file`) + data pipeline | `backend/.env` | `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` (auth + job_postings; service-role key, server-only), `OPENAI_API_KEY` / `OPENAI_MODEL` (LLM roadmaps), `CHROMA_*`, `RAG_TOP_K`, `REQUIREMENTS_*` (market-skill thresholds), `MATCHER_MODEL_PATH` |
| frontend | `frontend/.env` | `VITE_API_BASE_URL` (default `http://localhost:8000` — the gateway) |

Container-specific values (`CHROMA_PATH=/store/chroma`, `DAPR_ENABLED`,
`CORS_ORIGINS`) are pinned per service in `docker-compose.yml`.

## Tech stack

**Services:** FastAPI, Dapr 1.17 (invocation · pub/sub · state store, etag CAS),
Redis, Consul, nginx, ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`),
Supabase (GoTrue auth + Postgres `job_postings`), OpenAI (optional roadmaps),
pytest, Docker Compose.

**Frontend:** React 18, Vite, Tailwind CSS, framer-motion, lucide-react.

**Data pipeline:** `data/scripts/` — job-ad scrapers (httpx / RSS / jobspy),
skill extraction, RAG builder, matcher-training scripts.

## Project structure

```
Next_step_FP/
├── services/
│   ├── common/            # shared wire contracts: models, topics, config, Dapr client, auth dep, data JSONs
│   ├── questionnaire/     # questions + submit/select (publishes to Redis)
│   ├── matching/          # ChromaDB RAG + scoring (+ /internal/match, /internal/field-skills)
│   ├── roadmap/           # static/LLM roadmaps + market requirements + progress
│   ├── auth/              # Supabase GoTrue + usernames (+ /internal/verify)
│   ├── history/           # submissions in the Dapr state store (subscribers + history routes)
│   ├── gateway/nginx.conf # path routing on :8000
│   └── dapr/              # sidecar components (Redis) + config (Consul resolver)
├── docker-compose.yml     # 5 app+sidecar pairs · redis · consul · gateway
├── frontend/src/          # App.jsx (single-page SPA), api.js, data.js (offline fallback), pages/
├── backend/               # venv (test runner) · .env (secrets) · Supabase migrations — the pre-split
│                          #   monolith was removed at the microservices cutover
├── data/
│   ├── scripts/           # scrapers, extract_skills, build_rag, matcher training
│   └── jobs/              # raw/*.json + chroma/ (gitignored)
└── docs/                  # architecture.md · dapr.md · matching-rework-plan.md
```

## License

MIT
