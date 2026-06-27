# Deploying the backend to Hugging Face Spaces (Docker)

The FastAPI backend (`backend/app/`) deploys to a **Hugging Face Space (Docker SDK)** on
the free CPU Basic tier. The ChromaDB vector store is **baked into the image** at build
time from the committed raw job JSON — no persistent volume, and an empty store fails the
build (see `Dockerfile`).

## 1. Space README front-matter (required)

HF reads config from YAML front-matter in the Space's `README.md`. The repo `README.md` is
legacy and has none, so when you push, the Space `README.md` must start with this block
(prepend it, or use a dedicated README on the Space remote):

```yaml
---
title: Next Step Career API
emoji: 🧭
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
```

`app_port: 7860` must match the `--port 7860` in the `Dockerfile` CMD.

## 2. Secrets & variables (Space → Settings → Variables and secrets)

The Dockerfile sets `CHROMA_PATH` itself. Everything else is deploy-specific — set as
**Secrets** (sensitive) or **Variables** (non-sensitive). All are optional except CORS:

| Name | Type | Value |
|---|---|---|
| `CORS_ORIGINS` | Variable | Your frontend's public origin, e.g. `https://your-frontend.vercel.app` (comma-sep for multiple) |
| `SUPABASE_URL` | Secret | (optional) enables persistence + job_postings skill signal |
| `SUPABASE_SERVICE_KEY` | Secret | (optional) server-only service_role key |
| `OPENAI_API_KEY` | Secret | (optional) enables personalized roadmaps; falls back to static JSON if unset |

Do **not** set `CHROMA_PATH` — the image hardcodes the correct absolute path.

## 3. Frontend wiring

In the separately-deployed frontend, set `VITE_API_BASE_URL` to the Space's public URL:

```
VITE_API_BASE_URL=https://<your-username>-<space-name>.hf.space
```

…and rebuild the frontend. Then add that frontend origin to `CORS_ORIGINS` above (step 2).

## 4. Deploy (push to the Space remote)

```bash
# one-time: create the Space (Docker SDK) in the HF UI, then add it as a remote
git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
git push space main
```

HF builds the `Dockerfile`: installs CPU torch + deps, pre-caches the embedding model,
runs `build_rag.py` to embed ~1,575 ads into ChromaDB, and refuses to ship if the store is
empty. First build takes several minutes; subsequent builds reuse cached layers.

## 5. Refill / update the data later

There is **no in-place update** — the store is immutable inside the image. To refresh:

1. Update `data/jobs/raw/*.json` locally (re-scrape).
2. `git push space main`.
3. HF rebuilds; the `COPY data/` layer is invalidated, so `build_rag.py` re-runs and
   regenerates the store from the new JSON. App code changes alone do **not** rebuild it.

## 6. Verify it's live (and not the offline 503 fallback)

```bash
# health
curl https://<your-username>-<space-name>.hf.space/api/health

# real RAG path — should return recommendations, NOT a 503
curl -X POST https://<your-username>-<space-name>.hf.space/api/questionnaire/submit \
  -H "Content-Type: application/json" \
  -d '{"answers": {"q1":0,"q2":1,"q3":2,"q4":3,"q5":0,"q6":1,"q7":2,"q8":3,"q9":0,"q10":1}}'
```

A `200` with a `recommendations` array means the baked store is being read. A `503`
(`detail: service unavailable`) means the app fell back — check the Space build logs for
`baked N docs` and the startup line `ChromaDB collection 'job_ads' loaded`.
