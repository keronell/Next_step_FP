# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Most important thing to know

**The frontend SPA submits the questionnaire to a FastAPI backend (`backend/app/`), and falls back to a client-side matcher if that backend is down.**

`frontend/src/App.jsx::handleQuizComplete` POSTs answers via `frontend/src/api.js` to `POST /api/questionnaire/submit` (base URL from `VITE_API_BASE_URL`, default `http://localhost:8000`). The backend builds a natural-language profile, queries the existing ChromaDB `job_ads` store, and returns explainable RAG-blended recommendations. If the request fails, the SPA falls back to `computeResults` in `frontend/src/data.js` and shows an "offline estimate" notice — so it still works standalone with no backend.

The recommendations response is shaped to match what `Results.jsx` already renders (`id, title, description, keySkills, icon, roadmapKey, matchPercent`) plus `score`, `score_breakdown`, `reasons`, `matched_skills`, `missing_skills`. The backend mirrors the 6 careers + weights in `backend/app/data/careers.json` and the roadmaps in `backend/app/data/roadmaps.json`. Both still also live client-side in `data.js` as offline fallbacks (`Roadmap.jsx` fetches `GET /api/roadmap/{id}` and falls back to `ROADMAPS`).

Implications:
- To change the careers/weights, update **both** `frontend/src/data.js` (the offline fallback) and `backend/app/data/careers.json` (the live matcher), or they drift. Same for roadmaps: `frontend/src/data.js` `ROADMAPS` **and** `backend/app/data/roadmaps.json`.
- To change matching signals/weights, edit `backend/app/services/matching_service.py` (weights live in `FORMULA_WEIGHTS`, asserted to sum to 1).
- `README.md`, `SETUP.md`, and `start.js` still describe an **older, unused** architecture (Flask + SQLite + react-router hitting `/api` on `:3001`). That Flask app (`backend/app.py`) is vestigial — the live backend is the FastAPI app under `backend/app/`. The Vite proxy to `:3001` is also unused.
- `frontend/src/pages/AdaptiveQuestionnaire.jsx` is orphaned (imports `axios`, calls the old `/api`, not imported by `App.jsx`). It would break the build if imported. Ignore it.

## Commands

Frontend (from `frontend/`):

```bash
cd frontend
npm install
npm run dev      # dev server on http://localhost:3000
npm run build    # production build -> frontend/dist (use this to verify changes)
npm run preview  # serve the production build
```

There is no lint or frontend test runner. Verify frontend changes with `npm run build`.

FastAPI backend (live recommendation API):

```bash
backend/venv/bin/python -m pip install -r backend/requirements.txt
backend/venv/bin/python data/scripts/build_rag.py            # one-time: builds data/jobs/chroma (~1575 job ads)
cd backend && venv/bin/python -m uvicorn app.main:app --port 8000
cd backend && venv/bin/python -m pytest app/tests -q          # 15 tests, mock the vector store (no ChromaDB needed)
```

Ignore the root `npm start` / `./start.sh` / `start.js`, the Flask `backend/app.py`, and `SETUP.md` unless reviving that older flow.

## Frontend architecture

Single page, scroll-based, sections stacked in `App.jsx`. A `phase` string in `App.jsx` is the source of truth and gates what each section renders:

```
idle → assessing → loading → results_ready
```

- `handleStart` → `assessing` (scrolls to the Assessment section)
- `handleQuizComplete(answers)` → `loading`, then `await submitQuestionnaire(answers)` (`api.js`); on success stores the backend recommendations, on failure falls back to `computeResults(answers)` and sets `notice='offline'`, → `results_ready`. Guards against duplicate submits.
- `handleSelectCareer` sets `selectedCareer` and scrolls to the Roadmap section
- `handleReset` → back to `idle`

Sections (`frontend/src/pages/`): `Landing.jsx` (Hero), `HowItWorks.jsx`, `Questionnaire.jsx` (exported as `Assessment`), `Results.jsx`, `Roadmap.jsx`. Each receives `phase` and renders null / a sub-view based on it (e.g. `Questionnaire` internally switches between `answering`, `review`, and `loading` screens).

`data.js` exports: `QUESTIONS`, `CAREERS`, `computeResults(answers)` (the client-side matcher returning top matches), and `ROADMAPS` (keyed by career id).

## Styling

Tailwind (`frontend/tailwind.config.js`) with a custom theme: `cream` / `navy` / `gold` color tokens (backed by CSS variables in `frontend/src/index.css`), plus custom `font-display` / `font-body`, radius (`rounded-card`), and duration (`duration-base` / `duration-fast`) tokens. Animations use `framer-motion`; icons come from `lucide-react`. Reuse these tokens rather than hardcoding values.

## Backend

- `backend/app/` — **live** FastAPI recommendation API (the one the SPA calls). Structure: `main.py` (lifespan loads the embedding model + ChromaDB collection once, CORS, exception handlers), `api/routes/` (`health`, `questionnaire`, `roadmap`), `models/` (Pydantic request/response), `services/` (`profile` → NL query, `rag_service` → ChromaDB wrapper, `matching_service` → explainable blend, `roadmap_service` → roadmap lookup (LLM seam), `persistence` → best-effort Supabase writer), `repositories/career_repository.py` (catalog + RAG → candidates; `FakeCareerRepository` for tests), `data/` (careers/questions JSON), `tests/`. Config via env in `core/config.py` (`backend/.env.example`). The matching formula and assumptions are documented at the top of `matching_service.py`.
- **Roadmaps:** `GET /api/roadmap/{career_id}` returns `{ sections: [...] }` from `data/roadmaps.json` via `services/roadmap_service.py::get_roadmap` (404 for unknown ids). `get_roadmap` is the **seam for later personalization** — swap its body for a Claude-generated, profile-aware roadmap and the signature/shape stay the same. `Roadmap.jsx` fetches this and falls back to client `ROADMAPS` if the backend is down.
- **Persistence:** `/submit` schedules `services/persistence.py::save_submission` as a FastAPI `BackgroundTask`, inserting one row into the Supabase `public.submissions` table (`request_id`, `answers` jsonb, `recommendations` jsonb, `session_id`, `selected_career`). `POST /api/questionnaire/select` (`{session_id, career_id}`) schedules `save_selection`, which sets `selected_career` on the session's row (last-write-wins). The frontend mints an anonymous `session_id` (localStorage UUID, `api.js::getSessionId`) and sends it on both submit and select. All persistence is **best-effort** — disabled when `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` are unset (the default, incl. tests), and swallows errors so a DB outage never breaks a request. The service_role key is server-only; never expose it to the browser. Schema lives in two Supabase migrations — `create_submissions` and `add_session_and_selection` (RLS enabled, no policies — service_role bypasses it, browser keys get no access); recreate via the Supabase MCP if standing up a fresh project. MCP server config lives in `.mcp.json` (authenticate via `/mcp`). Roadmap generation/personalization is not yet persisted.
- `backend/app.py` — **old** Flask + SQLite REST API (sessions, roadmaps). Vestigial, not consumed by the frontend.
- ChromaDB store lives at `data/jobs/chroma/` (gitignored), collection `job_ads`, cosine space, `all-MiniLM-L6-v2`, built by `data/scripts/build_rag.py`. The backend only reads it — do not re-ingest per request.
- `data/` (repo root) — a separate data-engineering pipeline (scrapers, jobs, config, reports). The ingestion pipeline is considered complete; reuse `build_rag.py`, don't rebuild it.

## Branches

Active branches: `main`, `Ronen`, `vlad`. The current SPA frontend came from the `Ronen` redesign; `vlad` contributed the adaptive quiz and data pipeline. When merging frontend work, keep `main` and `Ronen` in sync.
