# Dapr runbook (DEV-38)

The backend uses the [Dapr](https://dapr.io) sidecar for state management and
pub/sub instead of writing Supabase directly:

- **State store** (`statestore`, Redis): submission records (`sub:{request_id}`),
  session/user indexes (`idx:session:{id}`, `idx:user:{id}`), roadmap progress
  (`progress:{user_id}:{career_id}`), and timestamped race markers
  (`claim:{session_id}` claim windows, `sel:{session_id}` latest click) that let
  a claim or selection delivered *before* its submission event still apply on
  arrival — but only to records already submitted when the marker was written,
  so a post-logout anonymous submission on the same browser is never claimed by
  the previous account. Marker TTL (7 days) is garbage collection only; the
  timestamps are what scope their effect. See
  `backend/app/services/submission_store.py`.
- **Pub/sub** (`pubsub`, Redis): `POST /api/questionnaire/submit` publishes a
  `submissions` event, `/select` publishes `selections` — replacing FastAPI
  BackgroundTasks. The app subscribes to its own topics (`/dapr/subscribe` →
  `/events/*`) and the subscriber writes the state store. At-least-once delivery;
  the writes are idempotent.
- Supabase remains for **auth** (GoTrue + `user_profiles`) and **job_postings**
  reads. `DAPR_ENABLED=false` (the default) degrades exactly like the old
  Supabase-off mode: persistence is a no-op, roadmap progress and submission
  history return 503.

## One-time setup

```bash
brew install dapr/tap/dapr-cli   # Dapr CLI
dapr init                        # needs Docker running; starts dapr_redis on :6379
```

`dapr init` gives you the Redis container the components in `dapr/components/`
point at. Verify with `docker ps | grep dapr_redis`.

## Run the backend with its sidecar

```bash
# backend/.env: set DAPR_ENABLED=true
cd backend
dapr run \
  --app-id nextstep-backend \
  --app-port 8000 \
  --resources-path ../dapr/components \
  -- ./venv/bin/python -m uvicorn app.main:app --port 8000
```

`dapr run` exports `DAPR_HTTP_PORT` into the app process; the app reads it via
`Settings.dapr_http_port`. If uvicorn dies, restart the whole `dapr run` —
the sidecar reads `/dapr/subscribe` only once at startup.

**Securing both directions:** Dapr has two independent token flows, both carried
in a `dapr-api-token` header:

- `APP_API_TOKEN` (sidecar → app): `/events/*` mutate state from event payloads
  (including `user_id`), so anything that can reach the app port could forge
  them. Locally that's fine — uvicorn binds 127.0.0.1 and the token is optional.
  Wherever the app binds 0.0.0.0 (docker-compose), set it: daprd sends it on
  every delivery and the app 401s everything without it.
- `DAPR_API_TOKEN` (app → sidecar): when daprd requires API auth, the backend
  attaches this token to every state/publish call (`dapr_client.py`) — without
  it, persistence/history/progress would all 401.

For a fully secured local run (both processes inherit `dapr run`'s environment):
`APP_API_TOKEN=$(openssl rand -hex 16) DAPR_API_TOKEN=$(openssl rand -hex 16) DAPR_ENABLED=true dapr run ...`

## Smoke test

```bash
curl -s localhost:8000/api/health | jq .
curl -s localhost:8000/dapr/subscribe | jq .        # 2 subscriptions

RID=$(curl -s -X POST localhost:8000/api/questionnaire/submit \
  -H 'Content-Type: application/json' \
  -d '{"answers":{"q1":1,"q2":2,"q3":3,"q4":0,"q5":1,"q6":2,"q7":3,"q8":0,"q9":1,"q10":2},"session_id":"smoke-1"}' \
  | jq -r .request_id)
sleep 1   # event round-trips through the broker

curl -s localhost:3500/v1.0/state/statestore/sub:$RID | jq .
curl -s localhost:3500/v1.0/state/statestore/idx:session:smoke-1 | jq .

curl -s -X POST localhost:8000/api/questionnaire/select \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"smoke-1","career_id":"frontend"}'
sleep 1
curl -s localhost:3500/v1.0/state/statestore/sub:$RID | jq .selected_career   # "frontend"
```

With Supabase creds set, the auth flow works end to end: register → login →
`POST /api/auth/claim-sessions {"session_id":"smoke-1"}` → `GET /api/auth/my-submissions`
returns the smoke submission.

Tests never need a sidecar: `cd backend && venv/bin/python -m pytest app/tests -q`
runs with `DAPR_ENABLED=false` and dict-backed fakes.
