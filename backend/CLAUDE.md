# Backend directory guidance

Loaded when working under `backend/`. **The FastAPI monolith that used to live at
`backend/app/` was deleted after the DEV-43 microservices cutover** — the live
backend is the five services under `services/` behind the nginx gateway
(`docs/architecture.md`; Dapr building blocks + state schema in `docs/dapr.md`).

What remains here and why:

- `venv/` — the Python environment used to run the per-service test suites
  (`cd services/<name> && ../../backend/venv/bin/python -m pytest tests -q`) and
  the data pipeline (`data/scripts/build_rag.py`). Rebuild it from
  `requirements.txt` (superset of every service's deps).
- `.env` / `.env.example` — env for the data pipeline (Supabase upsert in
  `build_rag.py`) and the source docker-compose reads the Supabase secrets
  from (`env_file` on the auth/matching/roadmap services). `APP_API_TOKEN` for
  compose comes from the REPO-ROOT `.env` instead — see both `.env.example`s.
- `migrations/` — the Supabase SQL history. Still-live tables: `user_profiles`
  (auth-service), `job_postings` (matching-service reads). `submissions` and
  `roadmap_progress` are legacy — that data moved to the Dapr state store and
  the old rows are intentionally not migrated.
- `config/`, `data/`, `scripts/` — legacy artifacts of the pre-SPA Flask /
  adaptive-quiz era (predates the monolith too). Not used by anything live.
