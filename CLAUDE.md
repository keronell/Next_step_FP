# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Detailed guidance is split by area: `frontend/CLAUDE.md` (SPA architecture, styling, roadmap canvas) and `backend/CLAUDE.md` (FastAPI services, persistence, auth, deployment) — each auto-loads when working under its directory.

## Most important thing to know

**The backend is five microservices under `services/` (questionnaire, matching, roadmap, auth, history) behind an nginx gateway on :8000, glued by Dapr sidecars (DEV-38/DEV-43): service invocation east-west, Redis pub/sub for submission persistence, Redis state store for all data (submissions, roadmap progress) — full map + runbook in `docs/architecture.md`, Dapr building-block details in `docs/dapr.md`. Shared wire contracts (models, topics, config, the Dapr client, invoke-based auth dep) live in `services/common/` — change contracts THERE, never per-service.** The pre-split FastAPI monolith (`backend/app/`) was deleted at cutover; `backend/` retains only the venv (runs the service test suites: `cd services/<name> && ../../backend/venv/bin/python -m pytest tests -q`), `.env` (compose secrets source), and the Supabase migrations — see `backend/CLAUDE.md`. Supabase remains only for auth (GoTrue + `user_profiles`, owned by auth-service) and `job_postings` reads (matching-service); the old `public.submissions`/`roadmap_progress` tables are no longer read.

**The frontend SPA submits the questionnaire to that gateway (same `:8000` base URL as the old monolith — zero frontend changes), and falls back to a client-side matcher if the backend is down.**

`frontend/src/App.jsx::handleQuizComplete` POSTs answers via `frontend/src/api.js` to `POST /api/questionnaire/submit` (base URL from `VITE_API_BASE_URL`, default `http://localhost:8000`). The backend builds a natural-language profile, queries the existing ChromaDB `job_ads` store, and returns explainable RAG-blended recommendations. If the request fails, the SPA falls back to `computeResults` in `frontend/src/data.js` and shows an "offline estimate" notice — so it still works standalone with no backend.

The recommendations response is shaped to match what `Results.jsx` already renders (`id, title, description, keySkills, icon, roadmapKey, matchPercent`) plus `score`, `score_breakdown`, `reasons`, `matched_skills`, `missing_skills`. The backend mirrors the 16 careers + weights in `services/common/data/careers.json` and the roadmaps in `services/common/data/roadmaps.json`. Both still also live client-side in `data.js` as offline fallbacks (`Roadmap.jsx` fetches `GET /api/roadmap/{id}` and falls back to `ROADMAPS`).

Implications:
- To change the careers/weights, update **both** `frontend/src/data.js` (the offline fallback) and `services/common/data/careers.json` (the live catalog). Same for roadmaps: `frontend/src/data.js` `ROADMAPS` **and** `services/common/data/roadmaps.json`. Same for questions: `frontend/src/data.js` `QUESTIONS`/`WEIGHTS`/`BONUSES` **and** `services/common/data/questions.json`+`careers.json` — the SPA fetches `GET /api/questions` on load (`Questionnaire.jsx`) and falls back to the bundled `QUESTIONS`. `showIf` is declarative (`{q, in}`, serialized as `show_if` in the JSON); new questions must be **appended** (never inserted) so a fetch resolving mid-quiz keeps indices stable. q11–q18 are pure discriminators: zero weights, signal via per-option bonuses only (q14–q17 are career-family follow-ups gated on q2's four options; q18 is linear). Adding/removing questions **or careers** changes the learned-matcher feature layout (the vector is `2·questions + 3·careers` wide, so the career count matters too) — bump `FEATURE_VERSION` in `services/matching/app/services/feature_builder.py` (`QUESTION_IDS` derives from `questions.json`, the per-career blocks from `careers.json`); the old artifact is then refused and matching falls back to the formula until retrained. `services/matching/tests/test_question_bank.py` enforces the bank's DoD: no two questions share a matching signal, every career ranks #1 for its archetype.
- To change matching signals/weights, edit `services/matching/app/services/matching_service.py` (weights live in `FORMULA_WEIGHTS`, asserted to sum to 1).
- **Learned matcher (opt-in):** when `MATCHER_MODEL_PATH` is set (see `backend/.env.example`), `match()` scores with a logistic-regression artifact (`data/models/matcher_logistic_v1.json`, loaded once in the `main.py` lifespan) instead of the formula — same response shape plus `model_version`; reasons come from exact linear attribution (`matcher_model.py` + `reason_builder.py`), features from the shared `feature_builder.py` (bump `FEATURE_VERSION` on layout changes; artifacts are refused on mismatch). Any model error falls back to the formula. **The checked-in artifact is stale: it was trained on the old 6-career catalog (`features-v1`) and is refused by the current `features-v3` layout, so `MATCHER_MODEL_PATH` defaults to blank in `.env.example` until a retrain re-exports it. It is also trained on synthetic LLM-panel silver labels — prototype quality, not expert-validated**; pipeline + retraining: `docs/matching-rework-plan.md`, scripts under `data/scripts/` (`panel_label_profiles.py` → `build_training_set.py` → `evaluate_matchers.py` / `train_models.py` → `export_model.py`). All these scripts derive the question set from `questions.json` (never hardcode `q1..qN`), so new questions flow into synthetic profiles, archetypes, and training automatically — but a **retrain is still required** for the model to actually use them.
- The old Flask + SQLite backend (`backend/app.py`, `backend/db/`, `backend/scripts/seed.py`), the orphaned `frontend/src/pages/AdaptiveQuestionnaire.jsx`, the `start.js`/`start.sh`/`start.bat` launchers, and `SETUP.md` have been **deleted**; the Vite proxy to `:3001` in `vite.config.js` is dead config (api.js always calls the absolute base URL). `README.md` now documents the microservices stack.

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

Microservices stack (the live backend — full runbook in `docs/architecture.md`):

```bash
backend/venv/bin/python data/scripts/build_rag.py   # one-time: builds data/jobs/chroma (~1575 job ads)
# secrets: cp .env.example .env (APP_API_TOKEN); Supabase creds in backend/.env
docker compose up -d --build                        # 13 containers; gateway on :8000
cd services/<name> && ../../backend/venv/bin/python -m pytest tests -q   # per-service suites
```

Sidecar/app pairs share a netns — restart them **together** (`docker compose restart matching matching-dapr`).

(The pre-split monolith was deleted at cutover — `backend/requirements.txt` remains only to rebuild the test venv.)

## Branches

Active branches: `main`, `Ronen`, `vlad`. The current SPA frontend came from the `Ronen` redesign; `vlad` contributed the adaptive quiz and data pipeline. When merging frontend work, keep `main` and `Ronen` in sync.
