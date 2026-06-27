# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Most important thing to know

**The frontend SPA submits the questionnaire to a FastAPI backend (`backend/app/`), and falls back to a client-side matcher if that backend is down.**

`frontend/src/App.jsx::handleQuizComplete` POSTs answers via `frontend/src/api.js` to `POST /api/questionnaire/submit` (base URL from `VITE_API_BASE_URL`, default `http://localhost:8000`). The backend builds a natural-language profile, queries the existing ChromaDB `job_ads` store, and returns explainable RAG-blended recommendations. If the request fails, the SPA falls back to `computeResults` in `frontend/src/data.js` and shows an "offline estimate" notice — so it still works standalone with no backend.

The recommendations response is shaped to match what `Results.jsx` already renders (`id, title, description, keySkills, icon, roadmapKey, matchPercent`) plus `score`, `score_breakdown`, `reasons`, `matched_skills`, `missing_skills`. The backend mirrors the 6 careers + weights in `backend/app/data/careers.json` and the roadmaps in `backend/app/data/roadmaps.json`. Both still also live client-side in `data.js` as offline fallbacks (`Roadmap.jsx` fetches `GET /api/roadmap/{id}` and falls back to `ROADMAPS`).

Implications:
- To change the careers/weights, update **both** `frontend/src/data.js` (the offline fallback) and `backend/app/data/careers.json` (the live matcher), or they drift. Same for roadmaps: `frontend/src/data.js` `ROADMAPS` **and** `backend/app/data/roadmaps.json`.
- To change matching signals/weights, edit `backend/app/services/matching_service.py` (weights live in `FORMULA_WEIGHTS`, asserted to sum to 1).
- The old Flask + SQLite backend (`backend/app.py`, `backend/db/`, `backend/scripts/seed.py`), the orphaned `frontend/src/pages/AdaptiveQuestionnaire.jsx`, the `start.js`/`start.sh`/`start.bat` launchers, and `SETUP.md` have been **deleted**. `README.md` still describes that older architecture (Flask + SQLite + react-router on `:3001`) and is **outdated** — the live backend is the FastAPI app under `backend/app/`; the Vite proxy to `:3001` is unused.

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
cd backend && venv/bin/python -m pytest app/tests -q          # 49 tests, mock the vector store + Supabase (no ChromaDB/DB needed)
```

Ignore `README.md`, which still documents the old (now-removed) Flask + SQLite flow.

## Frontend architecture

Single page, scroll-based, sections stacked in `App.jsx`. A `phase` string in `App.jsx` is the source of truth and gates what each section renders:

```
idle → assessing → loading → results_ready
```

- `handleStart` → `assessing` (scrolls to the Assessment section)
- `handleQuizComplete(answers)` → `loading`, then `await submitQuestionnaire(answers)` (`api.js`); on success stores the backend recommendations, on failure falls back to `computeResults(answers)` and sets `notice='offline'`, → `results_ready`. Guards against duplicate submits.
- `handleSelectCareer` sets `selectedCareer` and scrolls to the Roadmap section
- `handleLoadHistory(recommendations)` → `results_ready` directly from a saved submission (no questionnaire step); used by the History panel
- `handleReset` → back to `idle`

Sections (`frontend/src/pages/`): `Landing.jsx` (Hero), `HowItWorks.jsx`, `Questionnaire.jsx` (exported as `Assessment`), `Results.jsx`, `Roadmap.jsx`, `History.jsx` (logged-in users only, below Roadmap), `AuthModal.jsx` (modal, rendered in `App.jsx` — state lifted there so `handleStart` can open it directly). Each receives `phase` and renders null / a sub-view based on it (e.g. `Questionnaire` internally switches between `answering`, `review`, and `loading` screens). `History.jsx` ignores `phase` entirely — it renders whenever `user !== null`.

**Assessment gating:** The assessment is locked behind auth. `handleStart` in `App.jsx` returns early and opens the auth modal when `!user`. `Landing.jsx` (Hero CTA) and `Questionnaire.jsx` (`AssessmentStart`) show a Lock icon + "Sign in to …" button when `!user && !authLoading`; both still call `onStart` — the guard in `handleStart` does the routing. `authLoading=true` optimistically shows the unlocked state to avoid a flash for returning users.

`data.js` exports: `QUESTIONS` (full 10-question catalog), `visibleQuestions(answers)`, `CAREERS`, `computeResults(answers)` (the client-side matcher returning top matches), and `ROADMAPS` (keyed by career id).

**Adaptive branching:** the questionnaire asks an in-order *subset* of `QUESTIONS`, not all 10. A question may carry a `showIf(answers)` predicate; `visibleQuestions(answers)` filters `QUESTIONS` by it. `Questionnaire.jsx` derives `path = useMemo(visibleQuestions(answers))` and navigates that (index-based `currentQ`/`highWater`/dots/Back all index into `path`). Currently `q3` and `q9` are conditional on `q2`, so the path is 8–10 questions. **Invariant: a `showIf` may reference only *earlier* questions** (lower `QUESTIONS` index) — that keeps indices `0..currentQ` stable when the path recomputes mid-flow. On submit, answers are pruned to visible questions (`visibleAnswers()`), so the object handed to `handleQuizComplete` stays `{ qId: number | null }` but may omit branched-away keys. This is safe: the backend `QuestionnaireSubmission` accepts a partial map (rejects only *unknown* q-ids, requires ≥1 non-null), and both matchers treat a missing key as 0 (`answers.get(qid)` / `answers[q.id] ?? 0`).

**Auth context:** `frontend/src/contexts/AuthContext.jsx` provides `AuthProvider` (mounted in `main.jsx` wrapping `<App>`) and the `useAuth()` hook. `useAuth()` returns `{ user, authLoading, signIn, signUp, signOut }`. `user` is `{ user_id, email, username }` or `null` — `username` is the display name chosen at registration (falls back to `""` for sessions predating the username system; `Header.jsx` shows `user.username || user.email` so the nav is never blank); `authLoading` is `true` during the initial `GET /api/auth/me` rehydration on mount (prevents a "Sign In" flash for returning users). Tokens are stored in localStorage as `nextstep_access_token` and `nextstep_refresh_token`. `api.js` exposes a `_request` helper that auto-attaches `Authorization: Bearer <token>` to every fetch — no call site needs to handle this manually. `api.js` exports: `signUp(email, password, username)`, `signIn`, `signOut`, `getMe`, `claimSessions`, `fetchMySubmissions`.

## Styling

Tailwind (`frontend/tailwind.config.js`) with a custom theme: `cream` / `navy` / `gold` color tokens (backed by CSS variables in `frontend/src/index.css`), plus custom `font-display` / `font-body`, radius (`rounded-card`), and duration (`duration-base` / `duration-fast`) tokens. Animations use `framer-motion`; icons come from `lucide-react`. Reuse these tokens rather than hardcoding values.

## Backend

- `backend/app/` — **live** FastAPI recommendation API (the one the SPA calls). Structure: `main.py` (lifespan loads the embedding model + ChromaDB collection once, CORS, exception handlers), `api/routes/` (`health`, `questionnaire`, `roadmap`, `auth`), `models/` (Pydantic request/response — incl. `auth.py` for auth models), `services/` (`profile` → NL query, `rag_service` → ChromaDB wrapper, `matching_service` → explainable blend, `roadmap_service` → static + OpenAI roadmap generation, `job_postings_service` → Postgres skill reads, `supabase_client` → shared lazy client, `persistence` → best-effort Supabase writer, `auth_service` → Supabase GoTrue wrapper, **not** best-effort), `repositories/career_repository.py` (catalog + RAG + Postgres skills → candidates; `FakeCareerRepository` for tests), `data/` (careers/questions/roadmaps JSON), `migrations/` (SQL), `tests/`. Config via env in `core/config.py` (`backend/.env.example`). The matching formula and assumptions are documented at the top of `matching_service.py`.
- **Roadmaps:** `GET /api/roadmap/{career_id}` returns the static `{ sections: [...] }` from `data/roadmaps.json`; `POST /api/roadmap/{career_id}` (body `{profile?, missing_skills}`) returns a **personalized** roadmap. Both go through `services/roadmap_service.py::get_roadmap`, which calls **OpenAI** (`OPENAI_API_KEY`/`OPENAI_MODEL`) to generate a roadmap in the same schema when a key + context are present, and **falls back to the static JSON** on no key / no context / any LLM error (so the response always renders). `Roadmap.jsx` POSTs the selected career's `missing_skills` and falls back to client `ROADMAPS` if the backend is down. (404 for unknown ids.)
- **Persistence:** `/submit` schedules `services/persistence.py::save_submission` as a FastAPI `BackgroundTask`, inserting one row into the Supabase `public.submissions` table (`request_id`, `answers` jsonb, `recommendations` jsonb, `session_id`, `selected_career`, `user_id`, `created_at`). `POST /api/questionnaire/select` (`{session_id, career_id}`) schedules `save_selection`, which sets `selected_career` on the session's row (last-write-wins). The frontend mints an anonymous `session_id` (localStorage UUID, `api.js::getSessionId`) and sends it on both submit and select. All persistence is **best-effort** — disabled when `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` are unset (the default, incl. tests), and swallows errors so a DB outage never breaks a request. The service_role key is server-only; never expose it to the browser. Schema lives in Supabase migrations — `001_job_postings.sql`, `002_user_auth_link.sql` (adds nullable `user_id` FK + `created_at` to submissions; RLS enabled, no policies — service_role bypasses it), `003_user_profiles.sql` (username store); recreate via the Supabase MCP if standing up a fresh project. MCP server config lives in `.mcp.json` (authenticate via `/mcp`). Roadmap generation/personalization is not yet persisted.
- **Auth:** Routes under `api/routes/auth.py` proxy Supabase GoTrue — `POST /api/auth/register` (admin create, auto-confirmed), `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/claim-sessions`, `GET /api/auth/my-submissions`. All auth routes require `supabase_enabled = True`; they return **503** otherwise (auth is **never** best-effort, unlike persistence). Token verification uses `supabase_client.auth.get_user(jwt)` — no JWT secret needed in config. Protected routes use `get_current_user` from `api/deps.py` (raises 401 on missing/invalid token); `/submit` uses `get_current_user_optional` (returns `None` for anonymous users so the questionnaire flow is never blocked). The `sessions_id` anonymous flow continues to work unchanged alongside auth — on login, the frontend calls `POST /api/auth/claim-sessions` to link prior anonymous submissions to the new `user_id`. No Supabase JS SDK or anon key is exposed to the browser; all auth calls go through the FastAPI backend. **Deferred:** token refresh, email verification gate, password reset, per-IP rate limiting on auth endpoints.
- **Username system:** `POST /api/auth/register` accepts `RegisterRequest(email, password, username)` — a separate model from `AuthCredentials(email, password)` used for login. `username` is 3–30 chars, `^[a-zA-Z0-9_]+$`. `auth_service.register()` checks case-insensitive uniqueness via `ilike` on `public.user_profiles`, creates the GoTrue user, then inserts the profile row. `login()` and `get_user_from_token()` fetch the username from `user_profiles` via `_fetch_username()` (returns `""` if no row). `AuthTokenResponse` and `UserResponse` both include `username: str`. Schema: `public.user_profiles(user_id uuid PK FK auth.users, username text NOT NULL)` with a functional unique index on `lower(username)`; RLS enabled, no policies (service_role bypasses). Migration: `backend/migrations/003_user_profiles.sql`.
- **Job postings (Postgres):** `data/scripts/build_rag.py` upserts the scraped ads into the Supabase `public.job_postings` table (flow: scrape → raw JSON → Postgres upsert → ChromaDB embed; PK `id`, so re-runs don't duplicate). `services/job_postings_service.py::skill_counts` reads skills per field, and `career_repository.py` merges them into ChromaDB's market-skills signal — a graceful no-op when Supabase is unset (ChromaDB-only path). Schema in the `create_job_postings` migration (`backend/migrations/001_job_postings.sql`).
- ChromaDB store lives at `data/jobs/chroma/` (gitignored), collection `job_ads`, cosine space, `all-MiniLM-L6-v2`, built by `data/scripts/build_rag.py`. The backend only reads it — do not re-ingest per request.
- `data/` (repo root) — a separate data-engineering pipeline (scrapers, jobs, config, reports). The ingestion pipeline is considered complete; reuse `build_rag.py`, don't rebuild it.

## Deployment

**TLS terminates at the reverse proxy, not in the app.** Run the FastAPI backend
plain HTTP (uvicorn on a local port) behind a reverse proxy — nginx, Caddy, or a
cloud load balancer (e.g. an AWS ALB / Cloud Run / Fly proxy) — and let that layer
own HTTPS: certificates, redirects, and HTTP→HTTPS upgrade. Do **not** add
`ssl_keyfile`/`ssl_certfile` to uvicorn or any TLS handling in `app/main.py`; the
app stays transport-agnostic and the proxy forwards decrypted requests to it.

Practical notes:
- Point `CORS_ORIGINS` (in `backend/.env`) at the public HTTPS origin(s) of the frontend.
- Set the frontend's `VITE_API_BASE_URL` to the public HTTPS URL of the API.
- If the proxy sets `X-Forwarded-Proto`, run uvicorn with `--proxy-headers` so the app
  sees the original scheme.

## Branches

Active branches: `main`, `Ronen`, `vlad`. The current SPA frontend came from the `Ronen` redesign; `vlad` contributed the adaptive quiz and data pipeline. When merging frontend work, keep `main` and `Ronen` in sync.
