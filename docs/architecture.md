# Microservices architecture (DEV-38 + DEV-43)

The backend is five FastAPI services behind an nginx gateway, glued by Dapr
sidecars: service-to-service calls go through Dapr **service invocation**,
submission persistence flows through Dapr **pub/sub** (Redis Streams), and all
state lives in the Dapr **state store** (Redis). The React SPA is unchanged —
it talks to the gateway on `:8000`, the same base URL it always used.

```
                        ┌─────────────┐
   React SPA ──────────▶│   gateway   │ nginx :8000
                        └──┬─┬─┬─┬────┘
        /api/questionnaire │ │ │ │ /api/auth/my-submissions
              /api/questions│ │ │ │ /api/auth/claim-sessions
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
| **roadmap** | static+LLM roadmaps, DEV-59 market requirements, roadmap progress | `GET/POST /api/roadmap/{id}`, `GET/POST /api/roadmap/{id}/progress` | invokes matching + auth |
| **auth** | identity: Supabase GoTrue + `user_profiles` | `POST /api/auth/register\|login\|logout`, `GET /api/auth/me` | `GET /internal/verify` |
| **history** | submission records in the state store | `GET /api/auth/my-submissions`, `POST /api/auth/claim-sessions` | subscribes to both topics (`/events/*`, `/dapr/subscribe`) |

Key data shapes (state store, Redis — `:`-separated, `keyPrefix: none`):
`sub:{request_id}` submission records, `idx:session:{sid}` / `idx:user:{uid}`
indexes, `claim:{sid}` claim windows + `sel:{sid}` selection markers (TTL'd,
time-scoped — see `services/history/app/services/submission_store.py`),
`progress:{user_id}:{career_id}` roadmap progress.

Wire contracts live in `services/common/` (single source for models, topics,
config, the Dapr client, and the invoke-based auth dependency).

## Run it

```bash
# one-time: the matching corpus
backend/venv/bin/python data/scripts/build_rag.py

# secrets: cp .env.example .env  (APP_API_TOKEN — openssl rand -hex 16)
#          backend/.env — SUPABASE_URL/SUPABASE_SERVICE_KEY (+ OPENAI_API_KEY optional)

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
