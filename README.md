<div align="center">
  <img src="docs/assets/logo.png" alt="NextStep" width="420">
</div>

# NextStep Career Matcher

A career-discovery platform: a personalized assessment matches users to one of
**16 tech careers** with explainable, job-market-backed recommendations, then
generates a personal learning roadmap enriched with the skills employers
actually ask for.

[![NextStep walkthrough - User flow, from short quiz to the role selection and the roadmap](docs/assets/demo.gif)](docs/assets/demo.mp4)

   
**[Full walkthrough (35s) ▶](docs/assets/demo.mp4)** 

## User flow

1. **Create an account** - email, password and a username, handled by Supabase
   GoTrue. Signing up also claims any assessment you already took anonymously in
   the same browser, so nothing is lost by trying the quiz first.
2. **Answer the questionnaire** - about 15 questions in 3–5 minutes, on skills,
   work style and personality fit. The bank holds 18: the career-family
   follow-ups branch on your earlier answers, so you only see the relevant ones.
3. **Add a profile** *(optional)* - your experience, projects and the skills you
   already have. Skip it and the result is identical to not having the step at
   all. Fill it in and those skills both re-weight the score and make the
   "skills you have / still need" lists mean what they say.
4. **Get ranked matches** - the top 3 of 16 careers, each with a match
   percentage, the specific reasons behind it, and the skills you hold versus
   the ones you are missing.
5. **Choose a career** - your pick is recorded and unlocks that career's roadmap.
   A roadmap opens only for a career you hold a recommendation for: the same
   evidence that personalizes it is what authorizes it.
6. **Work the roadmap** - a visual skill graph where every node carries how often
   real job ads demand it. Tick nodes off as you learn them. Progress is saved
   per user and is still there when you come back.



## Architecture

![NextStep architecture - React SPA through the nginx gateway to five Dapr-glued services, backed by Supabase, ChromaDB and Redis, with an offline job-ad pipeline](docs/assets/architecture.png)


## Code map

Four things to read first, in the order a request touches them.

### RAG / vector search

Job ads are embedded **offline**: [build_rag.py](data/scripts/build_rag.py) turns each
scraped ad into one text blob (`build_document`) and upserts it into a persisted
ChromaDB collection `job_ads` (`get_client`, cosine space, `all-MiniLM-L6-v2`). At
request time nothing is re-ingested. [rag_service.py](services/matching/app/services/rag_service.py)
opens the collection and loads the model **once** in the matching-service lifespan,
then encodes the user's profile text and runs one metadata-filtered query per career
field.

```python
# RagService.query_field - services/matching/app/services/rag_service.py
result = self._collection.query(
    query_embeddings=[embedding], n_results=k,
    where={"field": field}, include=["metadatas", "distances"],
)
sims = [max(0.0, min(1.0, 1.0 - d)) for d in distances]  # cosine distance -> similarity
```

Look at: `RagService.create` / `encode` / `query_field`, and the caller
[career_repository.py](services/matching/app/repositories/career_repository.py).
`CareerRepository.get_candidates` embeds the profile once and fans out over the 16
careers. The query string itself is built by
[profile.py](services/matching/app/services/profile.py) `build_profile()`, which turns
the chosen answer options into `"I am …"` sentences. An optional self-input profile is
appended to it by [profile_text.py](services/common/profile_text.py)
(`profile_sentences`), and contributes nothing when skipped. Store
missing or empty ⇒ `RagUnavailableError` ⇒ 503, and the SPA shows its offline estimate.

### Supabase

Supabase is used for **auth and three tables only** (`user_profiles`,
`user_profile_data`, `job_postings`). The app's operational data
(submissions, roadmap progress) lives in the Dapr/Redis state store.
[supabase_client.py](services/common/supabase_client.py) builds two lazily-cached
clients, deliberately **not** the same instance. The split is about *user sessions*,
not about tables vs auth: `get_supabase_client()` stays service-role forever, so it
serves both `.table()` calls and GoTrue **admin** calls (`auth_service._get_admin_client`
- create_user, sign_out, list, delete). What must never touch it is a user-session
method (`sign_in_with_password`, `get_user`), because supabase-py then overwrites the
client's Authorization header with that user's JWT - downgrading it to `authenticated`
and re-enabling RLS on every later call. Those live on `get_auth_client()`.

```python
# services/common/supabase_client.py
@lru_cache
def get_supabase_client(): ...   # service-role: .table() + GoTrue admin
@lru_cache
def get_auth_client(): ...       # GoTrue user sessions only
```

Callers and tables:

- [auth_service.py](services/auth/app/services/auth_service.py) - GoTrue
  register/login/logout/me + `user_profiles` (usernames, `role`)
- [profile_service.py](services/auth/app/services/profile_service.py) -
  `user_profile_data`, one jsonb row per user (`get_profile` / `save_profile`)
- [job_postings_service.py](services/matching/app/services/job_postings_service.py) -
  read-only `skill_counts(field, limit)` over `job_postings`, degrades to an empty
  `Counter` when Supabase is off

Schema lives in [backend/migrations/](backend/migrations/) (`001_job_postings.sql` …
`006_user_role.sql`). Every path here returns 503 or an empty result rather than
crashing when `SUPABASE_*` is unset.

### FastAPI services

Five services, each `app/main.py` + `app/routes/` + `app/services/`, sharing wire
contracts from [services/common/](services/common/). Every app is built by one
factory. [app_factory.py](services/common/app_factory.py)
`create_app(title, routers, lifespan=)` adds CORS, `/healthz`, and a 500 handler
that keeps stack traces out of responses, so a service's `main.py` stays ~10 lines.

```python
# services/matching/app/main.py
app = create_app("Matching Service", [health.router, (internal.router, "")], lifespan=lifespan)
```

| Service | Entry point | Main routes | Service layer |
|---|---|---|---|
| questionnaire | [main.py](services/questionnaire/app/main.py) | [questions.py](services/questionnaire/app/routes/questions.py), [questionnaire.py](services/questionnaire/app/routes/questionnaire.py) - `submit` / `select` | [persistence.py](services/questionnaire/app/services/persistence.py) (publishes to Redis), [matching_client.py](services/questionnaire/app/matching_client.py) |
| matching | [main.py](services/matching/app/main.py) | [internal.py](services/matching/app/routes/internal.py) - `/internal/match` | [matching_service.py](services/matching/app/services/matching_service.py) `match()`, [matcher.py](services/matching/app/services/matcher.py) `load_matcher()` |
| roadmap | [main.py](services/roadmap/app/main.py) | [roadmap.py](services/roadmap/app/routes/roadmap.py) - roadmap + progress | [roadmap_service.py](services/roadmap/app/services/roadmap_service.py), [requirements_service.py](services/roadmap/app/services/requirements_service.py) |
| auth | [main.py](services/auth/app/main.py) | [auth.py](services/auth/app/routes/auth.py), [profile.py](services/auth/app/routes/profile.py), [admin.py](services/auth/app/routes/admin.py) | [auth_service.py](services/auth/app/services/auth_service.py), [profile_service.py](services/auth/app/services/profile_service.py) |
| history | [main.py](services/history/app/main.py) | [history.py](services/history/app/routes/history.py), [subscriptions.py](services/history/app/routes/subscriptions.py) (`/dapr/subscribe`, `/events/*`) | [submission_store.py](services/history/app/services/submission_store.py) |

Cross-service plumbing is all in `common/`: [dapr.py](services/common/dapr.py)
(`invoke`, `publish`, `save_state` with etag CAS),
[auth_dep.py](services/common/auth_dep.py) (`get_current_user` /
`get_current_user_optional`, which verify the JWT by invoking auth-service),
[models/](services/common/models/) (the Pydantic wire types),
[config.py](services/common/config.py). **Change a contract there, never per-service.**

### React frontend

No react-router and no Redux. [App.jsx](frontend/src/App.jsx) is one phase state
machine (`idle → assessing → profiling → loading → results_ready`) holding `answers`,
`profile` and `results` in `useState`. It owns the *run*, meaning the phase, the
shared answers/profile/results, and the reset/sign-out invalidation below. It does
not own the pages. Each one holds its own local state and does its own reads and
writes, so trace a load or a race to the page, not here (`Questionnaire.jsx` fetches the bank and holds the quiz,
`Profile.jsx` the draft and its save, `Roadmap.jsx` the graph and progress, `Admin.jsx`
the account list). Two shared pieces sit outside App:
[AuthContext.jsx](frontend/src/contexts/AuthContext.jsx) (session in context, tokens in
`localStorage`) and [useRoute.js](frontend/src/hooks/useRoute.js), a ~120-line path
router. It supplies `navigate`/`popstate` plus deferred scroll and history-open
targets, and the app reads it for both `/roadmap/{id}` deep links and the `/admin`
screen.

Every async continuation that can outlive a run re-checks a monotonic run id before
writing. `App.jsx` owns that decision because a child invalidating in an effect is
always a render behind:

```jsx
// frontend/src/App.jsx
const runIdRef = useRef(0)
useEffect(() => { runIdRef.current += 1 }, [user])   // sign-out / account switch invalidates the run
// ...later, after an await:
if (cancelled || runIdRef.current !== runId) return
```

- [api.js](frontend/src/api.js) - the only place that talks to the gateway.
  `_request()` attaches only `Content-Type` and the Bearer token. The anonymous
  `session_id` is added per call by the endpoints that correlate on it
  (`submitQuestionnaire`, `selectCareer`, `claimSessions`), so a new anonymous
  endpoint has to call `getSessionId()` itself. `VITE_API_BASE_URL` defaults to
  `http://localhost:8000`.
- [data.js](frontend/src/data.js) - bundled `QUESTIONS` / `CAREERS` / `ROADMAPS` +
  `computeResults()`, the **offline fallback** used when the backend is down. Keep it
  in sync with `services/common/data/*.json`.
- Pages: [Questionnaire.jsx](frontend/src/pages/Questionnaire.jsx) (fetches the bank,
  falls back to `QUESTIONS`), [Profile.jsx](frontend/src/pages/Profile.jsx) (optional
  self-input step), [Results.jsx](frontend/src/pages/Results.jsx),
  [Roadmap.jsx](frontend/src/pages/Roadmap.jsx) (skill-graph canvas, `fetchRoadmap` +
  `fetchRoadmapProgress`), [Admin.jsx](frontend/src/pages/Admin.jsx).

## Tech stack

**Services**

- **Python 3.12 + FastAPI + Pydantic** - all five backend services
- **Dapr 1.17.5** - service invocation, Redis pub/sub, state store (etag CAS)
- **Redis 7** - pub/sub broker and state (submissions, roadmap progress)
- **Consul 1.20** - service discovery for the Dapr sidecars
- **nginx 1.27** - API gateway, the single entry point on `:8000`
- **Supabase** - GoTrue auth, user profiles, job-posting reads
- **Docker Compose** - the whole stack, 13 containers, one command

**Frontend**

- **React 18 + Vite** - SPA, works offline when the backend is down
- **Tailwind CSS** - styling
- **framer-motion + lucide-react** - animation and icons

**Data pipeline**

- **ChromaDB** - vector store over the scraped job ads (1,853 scraped, all indexed)
- **sentence-transformers** (`all-MiniLM-L6-v2`) - embeddings for semantic matching
- **python-jobspy + feedparser + httpx** - job-ad scrapers in `data/scripts/`
- **Ollama + Qwen2.5 7B** - LLM panel that generates the silver training labels
- **PyTorch** - trains the neural matcher. Serving is a pure numpy forward pass, so no
  service depends on torch (see ADR 0005 and the learned-matcher section below)
- **scikit-learn** - logistic matcher and probability calibration
- **LightGBM** - benchmarked comparator, not shipped

How a submission flows:

```
questionnaire answers → POST /api/questionnaire/submit
  → matching-service builds a natural-language profile from the answers
  → queries the ChromaDB `job_ads` store (1,853 indexed ads, per career field)
  → blends semantic similarity + questionnaire fit + skill overlap into a score
  → top-3 explainable recommendations return to the SPA
  → the submission is published to Redis and persisted by history-service
```

## Quick start

Prerequisites: **Docker Desktop**, **Node 18+**, **Python 3.12**
(a venv at `backend/venv`, rebuildable from `backend/requirements.txt`).

```bash
# 0. one-time: build the job-ad vector store (1,853 indexed ads, all-MiniLM-L6-v2)
backend/venv/bin/python data/scripts/build_rag.py

# 1. secrets
cp .env.example .env            # set APP_API_TOKEN (openssl rand -hex 16)
cp backend/.env.example backend/.env   # optional: SUPABASE_* (auth)

# 2. everything at once (compose stack + Vite + browser):
./dev.sh                        # Windows: powershell -ExecutionPolicy Bypass -File dev.ps1

# - or manually -
docker compose up -d --build    # 13 containers - gateway on :8000
cd frontend && npm install && npm run dev   # SPA on :3000
```

All external services are optional: without Supabase, auth routes return 503
(the questionnaire still works anonymously). Without the ChromaDB store, matching
returns a safe 503 and the SPA shows its offline estimate. Roadmaps are always
curated static data. There is no generation step and nothing to configure.

Sidecars share their app's network namespace. Restart pairs together:
`docker compose restart matching matching-dapr`.

## Public API (through the gateway)

| Route | Service | Purpose |
|---|---|---|
| `GET /api/questions` | questionnaire | adaptive question bank |
| `POST /api/questionnaire/submit` | questionnaire | answers → recommendations |
| `POST /api/questionnaire/select` | questionnaire | record the chosen career |
| `GET /api/health` | matching | RAG store status (`rag_doc_count`) |
| `GET/POST /api/roadmap/{id}` | roadmap | curated roadmap (POST also adds in-demand market skills) |
| `GET/POST /api/roadmap/{id}/progress` | roadmap | per-user completed nodes (auth) |
| `POST /api/auth/register\|login\|logout`, `GET /api/auth/me` | auth | Supabase GoTrue + usernames |
| `GET/PUT /api/profile` | auth | self-input profile: experience, projects, skills (auth) |
| `GET /api/admin/users`, `DELETE /api/admin/users/{id}` | auth | account list + deletion (admin role only - DEV-62) |
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

This is the **formula matcher**. When the self-input profile (see below) carries at
least one skill tag, whether from the Skills section or a project's technologies,
the formula gains a fourth term taken from the two market-derived components. The
questionnaire keeps its weight:

```
final = 0.40 * questionnaire_fit + 0.30 * semantic_similarity
      + 0.10 * skill_overlap     + 0.20 * user_skill_match
```

A tag counts if it is **predominantly Latin script**, whether or not it is a skill
we recognize. `foobar` counts, a Hebrew tag does not. A profile of only
experience/project *prose* therefore keeps the three-term formula, while still
shifting the result through the embedding. A profile whose content is entirely
non-Latin moves neither: those tags and sentences are dropped from the embedding
query as well, leaving only the skill labels and `model_version` affected.

> **Known wart.** A tag we can't match against any career or job ad (`foobar`, or a
> real skill missing from the catalog like `Svelte 5`) still switches the fourth
> term on, where it scores 0 for every career. Each career then loses
> `0.10 * (semantic_similarity + skill_overlap)`. That is **not** a flat penalty.
> It bites hardest on the careers with the strongest semantic and market evidence. The tag
> separately enters the embedding query ("I know foobar."), moving
> `semantic_similarity` per career on its own. Between the two channels, entering a
> skill we don't recognize can both lower the percentages and reorder the results
> relative to skipping the step. Entering more information should never make your
> results worse. See `_profile_context()` in `matching_service.py` for where the
> gate would need to move.

### Self-input profile (optional step)

Between the questionnaire and the results, a signed-in user can enter work
experience, projects and skills. Everything about it is optional: skip it, or leave
it empty, and matching is byte-identical to the formula above.

Supplying one changes the result two ways. The prose is appended to the embedding
query (so `semantic_similarity` shifts toward the fields you actually have
background in) and your skills are scored against each career's key skills plus
that field's market demand. It also makes `matched_skills` / `missing_skills`
describe *you* rather than the job market, which is what colours the roadmap's
skill-gap nodes.

```bash
# same answers, with a profile -> different ranking and truthful skill lists
curl -s -X POST http://localhost:8000/api/questionnaire/submit \
  -H 'Content-Type: application/json' \
  -d '{"answers":{"q1":3,"q2":1,"q4":2,"q5":1,"q7":2,"q10":1},
       "profile":{"skills":["Python","SQL","Tableau"],
                  "experience":[{"role":"Data Analyst","context":"a fintech",
                                 "duration_months":24,
                                 "description":"built dashboards and SQL pipelines"}]}}'
```

Saved per user in Supabase `user_profile_data` via `GET/PUT /api/profile`, and
snapshotted onto each submission so restoring a past result restores the profile it
was scored with. English-only: the career catalog, job-ad corpus and embedding
model are all English, so non-Latin prose is excluded from the query rather than
degrading it.

- `questionnaire_fit` - per-career answer weights + bonuses, normalized against
  the strongest-fitting career.
- `semantic_similarity` - ChromaDB cosine distance converted to `1 - distance`.
- `skill_overlap` - share of a career's key skills present in the retrieved ads.

Weights live in
[matching_service.py](services/matching/app/services/matching_service.py)
(`FORMULA_WEIGHTS` and `PROFILE_WEIGHTS`), both asserted to sum to 1. The formula
is not the whole story any more. A learned model now chooses *which* careers get
scored. See below.

### Learned matcher (the MLP)

Since DEV-99 the stack ships with `MATCHER_MODEL_PATH` pointed at a trained neural
matcher, so the formula above is no longer the only thing deciding your results.

**What it is.** [matcher_nn_v1.json](data/models/matcher_nn_v1.json) - a
probability-averaged ensemble of 5 ReLU MLPs (trunk `84 → 64 → 32 → 16`, dropout
0.5, temperature 0.80), trained on 232 rows of synthetic LLM-panel silver labels.
Depth, widths and member count are all read from the artifact, not hardcoded.

**What it actually does in production: selection, not pricing.** Its pooled
out-of-fold ECE is 0.139, above the 0.1 ship floor, so its probabilities are not
trustworthy as percentages. Its *ranking* is trustworthy, and gets gated
separately. Top-2 stability is 0.735 against a 0.6 floor, which clears. Under ADR 0005 that combination ships as `ranking_only`.
The model picks which careers appear, and every number shown next to them (the
percentage, the score, the breakdown) is still the deterministic formula's, which
also sets their display order. The model's own probability is kept as
`score_breakdown.model_probability` so the choice stays auditable. The artifact
carries this restriction itself, in a `deployment` block every consumer must read.

**Where it is loaded.** [matcher.py](services/matching/app/services/matcher.py)
`load_matcher()` validates the artifact and dispatches on its `model_type`, so the
serving code depends on a `Matcher` protocol rather than any one model family.
[matcher_nn.py](services/matching/app/services/matcher_nn.py) runs the numpy
forward pass plus integrated-gradients attribution for the "why" reasons.
[feature_builder.py](services/matching/app/services/feature_builder.py) builds the
84-wide feature vector. Bump its `FEATURE_VERSION` whenever questions or careers
change, or the artifact is refused. Loading happens once in the matching-service
lifespan, and **any** error there falls back to the formula:

```
docker compose logs matching | grep 'Learned matcher loaded'
Learned matcher loaded: matcher-nn-v1
```

**Where it is trained.** [nn_model.py](data/scripts/nn_model.py) (`NNClassifier`,
`SeedEnsemble`), [train_models.py](data/scripts/train_models.py), exported by
[export_nn_model.py](data/scripts/export_nn_model.py). Run these in the training
venv, never `backend/venv` (see Tests).

**The alternative artifact.**
[matcher_logistic_v2.json](data/models/matcher_logistic_v2.json) is the calibrated
logistic model, with worse ranking and honest percentages. Point
`MATCHER_MODEL_PATH` at it to serve real model-derived numbers. `matcher_logistic_v1.json` is stale
(6-career `features-v1`) and is refused on load.

> **Prototype quality.** The labels are LLM-panel output that follows the
> hand-authored bonus table in `careers.json` about 94% of the time, not
> expert-validated ground truth. Game-dev has 5 labels (floor level) and frontend
> is over-represented at 20% of rows. The artifact's `caveats` list says all of
> this, and it rides through to the API response as `model_caveats`.

## Tests

Each service has an isolated suite. External calls are faked at seams, so no
Docker, sidecar, or database is needed:

```bash
cd services/<questionnaire|matching|roadmap|auth|history>
../../backend/venv/bin/python -m pytest tests -q
```

> If a suite fails for no apparent reason after you've reverted an edit, clear the
> stale bytecode first: `find services -name __pycache__ -type d -exec rm -rf {} +`.

The training and export pipeline has its own suite, and it runs in a **separate,
hash-pinned venv**. Never use `backend/venv` for the matcher training, evaluation
or export scripts - its installs move `numpy`/`pandas` out from under the recorded
`dataset_digest`, and the pipeline then refuses to reproduce. (The dependency-light
scripts, `build_rag.py` above included, run fine on `backend/venv`.)

```bash
python -m venv data/venv-training
data/venv-training/bin/python -m pip install --require-hashes -r data/requirements-training.txt
data/venv-training/bin/python -m pip install pytest   # deliberately not in the lockfile
data/venv-training/bin/python -m pytest data/scripts/tests -q
data/venv-training/bin/python data/scripts/evaluate_matchers.py   # must reproduce the recorded digest
```

Two platform caveats, because that lockfile is a single-machine reproduction
guarantee rather than a cross-platform one:

- **On Windows**, `Scripts/` replaces `bin/` in every venv path above. That is the
  platform the lock was compiled on.
- **On Linux or macOS**, the install above will fail. The lock was compiled by
  pip-compile under **Python 3.14 on Windows**, carries no environment markers, and
  omits the Linux-only torch CUDA dependencies, so `--require-hashes` cannot resolve
  it elsewhere. Recompile it there using the exact command in the header of
  [requirements-training.in](data/requirements-training.in), all three flags
  included, then re-run `evaluate_matchers.py`. If the digest moved, no number from
  that environment is comparable to recorded history.

`services/matching/tests/` also holds three diagnostics helpers that are scripts
rather than tests. Run `ig_diagnostics.py` (integrated-gradients completeness on a
real artifact) and `reason_diagnostics.py` with `--artifact <path>` when changing
the matcher -  `flip_diagnostics.py` takes no arguments - run it bare.

## Environment variables

Three scopes (they do not overlap):

| Scope | File | Keys |
|---|---|---|
| docker-compose interpolation | repo-root `.env` | `APP_API_TOKEN` - **required**. Gates history-service's event-ingestion endpoints. Also `MATCHER_MODEL_PATH` - see below |
| services (via `env_file`) + data pipeline | `backend/.env` | `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` (auth + job_postings - service-role key, server-only), `OPENAI_API_KEY` (read only by `backend/scripts/generate_expert_answers.py`, an offline quiz-data script - no service reads it), `CHROMA_*`, `RAG_TOP_K`, `REQUIREMENTS_*` (market-skill thresholds), `MATCHER_MODEL_PATH` (**local `dapr run` / uvicorn only** - see below) |
| frontend | `frontend/.env` | `VITE_API_BASE_URL` (default `http://localhost:8000` - the gateway) |

Container-specific values (`CHROMA_PATH=/store/chroma`, `DAPR_ENABLED`,
`CORS_ORIGINS`) are pinned per service in `docker-compose.yml`.

**`MATCHER_MODEL_PATH` appears in both scopes and only one of them wins under
compose.** `backend/.env`'s value reaches `auth` and `roadmap` through `env_file`,
and both ignore it. Only `services/matching/app/main.py` reads the setting, even
though `common/config.py` defines it for every service. For `matching`,
`docker-compose.yml`'s `environment:` key overrides `env_file:` and interpolates
the **repo-root** `.env` instead, which needs a *container* path
(`/store/models/...` - `data/models` is mounted read-only at `/store/models`).
Verify with `docker compose config` rather than by reading. The repo-root `.env`
sets it to `/store/models/matcher_nn_v1.json`. DEV-99 flipped it on 2026-08-04
after human approval, so the neural matcher serves. It supplies the **selection**
only: every displayed percentage is still the formula's, per ADR 0005's
mitigable-ECE branch. `backend/.env` still points at the stale `matcher_logistic_v1`,
which is refused on load and never reaches `matching` anyway.

**Rollback:** blank that one line and restart `matching` + `matching-dapr` together
(shared netns). No code redeploy. It does not rewrite already-persisted submissions,
which keep the `model_version`/`model_caveats` they were scored with.

**Changing the flag can require a rebuild, not just a restart.** An image built
before the DEV-88 dispatch seam has no `matcher.py`, so the neural artifact is
refused with `malformed model artifact ...: 'coef'`. That is the linear loader's
error, which reads like a bad artifact and is really a stale build. Use
`docker compose up -d --build matching matching-dapr` and confirm the
`Learned matcher loaded: matcher-nn-v1` line in `docker compose logs matching`.
Evidence and the decision: [dev-23-flip-readiness.md](docs/dev-23-flip-readiness.md),
[dev-23-nn-decision.md](docs/dev-23-nn-decision.md).

## Decision records

Anything that looks arbitrary in the matcher probably has an ADR explaining why.
[docs/adr/](docs/adr/):

| ADR | Subject |
|---|---|
| [0001](docs/adr/0001-vertical-stage-flow.md) | The SPA is one vertical stage flow, not routed pages |
| [0002](docs/adr/0002-roadmap-access.md) | A roadmap opens only for a career you hold a recommendation for |
| [0003](docs/adr/0003-admin-role.md) | The admin role is granted by SQL, never by an endpoint |
| [0004](docs/adr/0004-neural-matcher-is-a-project-requirement.md) | Why a neural matcher exists at all |
| [0005](docs/adr/0005-gate-1-is-a-ship-floor.md) | Gate 1 is a ship floor. The `ranking_only` split verdict |
| [0006](docs/adr/0006-residual-matcher-freezes-its-linear-branch.md) | The residual matcher's linear branch is frozen, not trained |
| [0007](docs/adr/0007-temperature-is-cross-fitted.md) | Calibration temperature is cross-fitted, not fitted on its own eval data |

## Project structure

```
Next_step_FP/
├── services/
│   ├── common/            # shared wire contracts: models, topics, config, Dapr client, auth dep, data JSONs
│   ├── questionnaire/     # questions + submit/select (publishes to Redis)
│   ├── matching/          # ChromaDB RAG + scoring (+ /internal/match, /internal/field-skills)
│   ├── roadmap/           # curated roadmaps + market requirements + progress
│   ├── auth/              # Supabase GoTrue + usernames + self-input profile (+ /internal/verify)
│   ├── history/           # submissions in the Dapr state store (subscribers + history routes)
│   ├── gateway/nginx.conf # path routing on :8000
│   └── dapr/              # sidecar components (Redis) + config (Consul resolver)
├── docker-compose.yml     # 5 app+sidecar pairs · redis · consul · gateway
├── frontend/src/          # App.jsx (single-page SPA), api.js, data.js (offline fallback), pages/
├── backend/               # venv (test runner) · .env (secrets) · migrations/ (Supabase schema)
│                          #   · scripts/ · config/ · data/ - the pre-split monolith itself
│                          #   was removed at the microservices cutover
├── data/
│   ├── scripts/           # scrapers, extract_skills, build_rag, matcher training + tests/
│   ├── jobs/              # raw/*.json + chroma/ (gitignored)
│   ├── models/            # shipped matcher artifacts (nn_v1, logistic_v2, stale logistic_v1)
│   └── training/          # datasets, sweep results, gate verdicts, evaluation reports
└── docs/                  # architecture.md · dapr.md · matching-rework-plan.md
```

## License

MIT
