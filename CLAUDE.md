# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Most important thing to know

**The frontend SPA submits the questionnaire to a FastAPI backend (`backend/app/`), and falls back to a client-side matcher if that backend is down.**

`frontend/src/App.jsx::handleQuizComplete` POSTs answers via `frontend/src/api.js` to `POST /api/questionnaire/submit` (base URL from `VITE_API_BASE_URL`, default `http://localhost:8000`). The backend builds a natural-language profile, queries the existing ChromaDB `job_ads` store, and returns explainable RAG-blended recommendations. If the request fails, the SPA falls back to `computeResults` in `frontend/src/data.js` and shows an "offline estimate" notice — so it still works standalone with no backend.

The recommendations response is shaped to match what `Results.jsx` already renders (`id, title, description, keySkills, icon, roadmapKey, matchPercent`) plus `score`, `score_breakdown`, `reasons`, `matched_skills`, `missing_skills`. The 6 careers and their roadmaps still live client-side in `data.js`; the backend mirrors the 6 careers + weights in `backend/app/data/careers.json`.

Implications:
- To change the careers/weights, update **both** `frontend/src/data.js` (the offline fallback) and `backend/app/data/careers.json` (the live matcher), or they drift.
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

- `backend/app/` — **live** FastAPI recommendation API (the one the SPA calls). Structure: `main.py` (lifespan loads the embedding model + ChromaDB collection once, CORS, exception handlers), `api/routes/` (`health`, `questionnaire`), `models/` (Pydantic request/response), `services/` (`profile` → NL query, `rag_service` → ChromaDB wrapper, `matching_service` → explainable blend), `repositories/career_repository.py` (catalog + RAG → candidates; `FakeCareerRepository` for tests), `data/` (careers/questions JSON), `tests/`. Config via env in `core/config.py` (`backend/.env.example`). The matching formula and assumptions are documented at the top of `matching_service.py`.
- `backend/app.py` — **old** Flask + SQLite REST API (sessions, roadmaps). Vestigial, not consumed by the frontend.
- ChromaDB store lives at `data/jobs/chroma/` (gitignored), collection `job_ads`, cosine space, `all-MiniLM-L6-v2`, built by `data/scripts/build_rag.py`. The backend only reads it — do not re-ingest per request.
- `data/` (repo root) — a separate data-engineering pipeline (scrapers, jobs, config, reports). The ingestion pipeline is considered complete; reuse `build_rag.py`, don't rebuild it.

## Branches

Active branches: `main`, `Ronen`, `vlad`. The current SPA frontend came from the `Ronen` redesign; `vlad` contributed the adaptive quiz and data pipeline. When merging frontend work, keep `main` and `Ronen` in sync.
