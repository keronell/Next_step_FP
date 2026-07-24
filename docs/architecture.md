# Microservices architecture (DEV-38 + DEV-43)

The backend is five FastAPI services behind an nginx gateway, glued by Dapr
sidecars: service-to-service calls go through Dapr **service invocation**,
submission persistence flows through Dapr **pub/sub** (Redis Streams), and
operational state — submissions, roadmap progress — lives in the Dapr **state
store** (Redis). Durable *account* data stays in Supabase: identity (GoTrue),
usernames (`user_profiles`) and the DEV-60 self-input profile
(`user_profile_data`), all owned by auth-service. The React SPA is unchanged —
it talks to the gateway on `:8000`, the same base URL it always used.

```
                        ┌─────────────┐
   React SPA ──────────▶│   gateway   │ nginx :8000
                        └──┬─┬─┬─┬────┘
        /api/questionnaire │ │ │ │ /api/auth/my-submissions
              /api/questions│ │ │ │ /api/auth/claim-sessions
                   /api/profile │ │
           ┌───────────────┘ │ │ └───────────────┐
           ▼                 ▼ ▼                 ▼
   ┌──────────────┐   ┌─────────┐  ┌───────┐  ┌─────────┐
   │questionnaire │   │ roadmap │  │ auth  │  │ history │◀─ pub/sub:
   └──────┬───────┘   └────┬────┘  └───▲───┘  └────▲────┘   submissions,
          │ invoke:        │ invoke:   │ invoke:   │        selections
          │ internal/match │ field-    │ internal/verify
          ▼                ▼ skills    │ (from questionnaire,
   ┌──────────────┐   ┌─────────┐     │  roadmap, history)
   │   matching   │   │matching │─────┘
   │ ChromaDB+ML  │   └─────────┘
   └──────────────┘
   Infra: redis (state + pub/sub broker), consul (sidecar name resolution)
```

## Service table

| Service | Owns | Public routes (gateway) | Internal surface |
|---|---|---|---|
| **questionnaire** | question bank, submission intake | `GET /api/questions`, `POST /api/questionnaire/submit`, `POST /api/questionnaire/select` | publishes `submissions`/`selections` |
| **matching** | ChromaDB store, embedding model, matching math, learned matcher, job_postings reads | `GET /api/health` | `POST /internal/match`, `GET /internal/field-skills?field=` |
| **roadmap** | curated static roadmaps, DEV-59 market requirements, roadmap progress | `GET/POST /api/roadmap/{id}`, `GET/POST /api/roadmap/{id}/progress` | invokes matching + auth |
| **auth** | identity: Supabase GoTrue + `user_profiles`; the DEV-60 self-input profile (`user_profile_data`) | `POST /api/auth/register\|login\|logout`, `GET /api/auth/me`, `GET/PUT /api/profile` | `GET /internal/verify` |
| **history** | submission records in the state store | `GET /api/auth/my-submissions`, `POST /api/auth/claim-sessions` | subscribes to both topics (`/events/*`, `/dapr/subscribe`) |

Key data shapes (state store, Redis — `:`-separated, `keyPrefix: none`):
`sub:{request_id}` submission records, `idx:session:{sid}` / `idx:user:{uid}`
indexes, `claim:{sid}` claim windows + `sel:{sid}` selection markers (TTL'd,
time-scoped — see `services/history/app/services/submission_store.py`),
`progress:{user_id}:{career_id}` roadmap progress.

Wire contracts live in `services/common/` (single source for models, topics,
config, the Dapr client, and the invoke-based auth dependency).

### Self-input profile (DEV-60)

An optional step between the questionnaire and the results — experience, projects
and skills the user enters themselves. It is the first matching input that is about
the **user** rather than the job market.

- **Storage is Supabase, not the state store.** `user_profile_data` (one jsonb row
  per user, migration `005`), owned by auth-service. A deliberate exception to the
  DEV-43 cutover: submissions are an event stream, whereas a profile is durable
  account data the user edits directly — the same reason `user_profiles` stayed.
- **It reaches matching inline**, in the submit that produces the recommendations
  (`QuestionnaireSubmission.profile` → `MatchRequest.profile`), not by a lookup from
  matching-service. One data path, and it works before/without a successful save.
- **Effect 1 — both scoring paths.** `common/profile_text.py` appends the profile to
  the embedding query, moving `semantic_similarity`. This also reaches the learned
  matcher through its `<career>_sem` features, with no retrain and no
  `FEATURE_VERSION` bump.
- **Effect 2 — the FORMULA path only.** A non-empty canonical skill set (Skills
  section plus project technologies) switches `matching_service.PROFILE_WEIGHTS`
  on, giving those skills 0.20 taken from the two market-derived components.
  `_match_model()` never reads `PROFILE_WEIGHTS` and never emits
  `user_skill_match`: re-weighting is a formula concept, and the model already sees
  the profile via its semantic features. So with `MATCHER_MODEL_PATH` set, a
  profile changes the score only through effect 1. No profile ⇒ byte-identical to
  the pre-DEV-60 formula.
- **Two gates, not one.** `_profile_context()` answers `has_profile` and
  `user_skills` independently. `user_skills` selects the weights; an
  experience-only profile keeps `FORMULA_WEIGHTS`, because a `user_skill_match` of
  0 for every career adds no discrimination while costing each career
  `0.10*(semantic_similarity + skill_overlap)` — not a flat penalty, it falls
  hardest on the best-evidenced careers. `has_profile` governs labeling **on both
  paths**, so such a profile still gets truthful skill lists.
  A tag joins `user_skills` by being predominantly Latin script, NOT by being in
  the alias map — so an unrecognized tag switches the weights on, scores 0, and
  takes exactly that hit while also entering the embedding query. See the "known
  wart" in `README.md`.
- **It also fixes a lie.** `matched_skills`/`missing_skills` were market-derived
  while `Roadmap.jsx` rendered them as "you may already have this skill". Whenever
  `has_profile` is true they finally describe the user.
- **A snapshot rides on each submission record** (`profile` in `sub:{request_id}`,
  surfaced by `GET /api/auth/my-submissions`) so restoring a past result restores
  the profile it was *scored with* — the live row is mutable.
- **English-only** (supersedes the ticket's Hebrew requirement): the catalog,
  corpus, alias map and MiniLM are all English, so non-Latin prose is kept out of
  the embedding rather than degrading it.

## Run it

```bash
# one-time: the matching corpus
backend/venv/bin/python data/scripts/build_rag.py

# secrets: cp .env.example .env  (APP_API_TOKEN — openssl rand -hex 16)
#          backend/.env — SUPABASE_URL/SUPABASE_SERVICE_KEY

docker compose up -d --build     # 13 containers: 5 apps + 5 sidecars + redis + consul + gateway
cd frontend && npm run dev       # SPA on :3000 -> gateway on :8000 (default base URL)
```

Sidecar/app pairs share a network namespace (`network_mode: service:<app>`), so
**always stop/start them together**: `docker compose restart matching matching-dapr`.
Resilience demo: `docker compose stop matching matching-dapr` → submits answer
503 and the SPA shows its offline estimate; start them again and it recovers in
~15s (Consul re-registration).

Per-service tests (no Docker/sidecar needed — external calls are faked):

```bash
cd services/<name> && ../../backend/venv/bin/python -m pytest tests -q
```

## Operational notes (learned the hard way)

- **Name resolution**: mDNS doesn't cross containers; Consul (dev mode) is the
  resolver. The SQLite alternative races itself on a shared volume — avoided.
- **Internal gRPC ports are pinned** (`--dapr-internal-grpc-port 50002`) so a
  restarted sidecar re-registers at a stable address.
- **Timeouts**: a full match runs ~6s in the compose topology (VM overhead) —
  `match_remote` budgets 30s over the Dapr client's 5s default.
- **Chroma volume is writable**: `PersistentClient` runs migrations + WAL on
  open; a `:ro` mount fails at startup.
- **Two Dapr token directions**: `APP_API_TOKEN` (sidecar→app; gates history's
  `/events/*` — required in compose, from the repo-root `.env`) and
  `DAPR_API_TOKEN` (app→sidecar, when daprd requires API auth). See
  `docs/dapr.md` for the DEV-38 single-process runbook and the state/pub-sub
  building-block details.
- The gateway never routes `/internal/*`, `/events/*`, or `/dapr/*` — verified
  404 publicly.
