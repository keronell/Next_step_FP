# NextStep — Workflow Redesign & Improvement Plan

> **Status (2026-06-24):** Historical planning doc. The redesign was largely implemented,
> but differently than proposed below:
> - **Job ads scraper + ChromaDB RAG — built** (`data/scripts/scrape_job_ads.py`, `build_rag.py`).
> - **Matching — built differently:** instead of a neural matcher, the live backend uses a
>   deterministic, explainable blend (questionnaire fit + semantic similarity + skill overlap)
>   in `backend/app/services/matching_service.py`. **The neural matcher was not built.**
> - **Roadmaps — served by the FastAPI backend** with optional LLM generation
>   (`backend/app/services/roadmap_service.py`); a Postgres `job_postings` table was added.
> - **The old Flask + SQLite backend referenced below (`backend/app.py`, `backend/db/`) was
>   removed** — line references such as `backend/app.py:183–224` no longer exist.
>
> Everything below is retained for historical context.

## Current Workflow (What Exists)

```
Question Bank (1,702 Qs)
       ↓ multi-label classification (40 labels)
LLM Expert Answers (Ollama) → per-role answer vectors
       ↓
Adaptive Quiz → eliminates roles by similarity to expert answers
       ↓
User Answers → Skill Vector (weighted sum, normalized 0-5)
       ↓
Role Matching → weighted arithmetic distance to hardcoded role requirements
       ↓
Roadmap → gap analysis → curated resources
```

### Core Weakness

The matching is purely geometric and hand-crafted:

```
score = Σ(user_level / required_level) * weight
```

This doesn't capture:
- Non-linear relationships between skills
- Skill substitution (TypeScript ≈ JavaScript)
- Contextual skill importance across roles
- Patterns from real job market data

Role requirements are hardcoded in the DB — not derived from actual hiring signals.

---

## Proposed Improved Workflow

```
┌─────────────────────────────────────────────────────┐
│  OFFLINE PIPELINE (runs periodically)               │
│                                                     │
│  Job Ads Scraper (LinkedIn/Indeed)                  │
│       ↓                                             │
│  NLP Feature Extraction                             │
│  (skills, experience, tech stack)                   │
│       ↓                                             │
│  Vector DB / RAG (ChromaDB)                         │
│  ← ground truth for role requirements               │
└─────────────────┬───────────────────────────────────┘
                  │ informs
                  ↓
┌─────────────────────────────────────────────────────┐
│  TRAINING PIPELINE                                  │
│                                                     │
│  LLM-annotated answers (answer_questions_local.py)  │
│  + RAG-extracted role features                      │
│       ↓                                             │
│  Train Neural Matcher                               │
│  Input: user_vector → Output: P(field) per field    │
└─────────────────┬───────────────────────────────────┘
                  │ serves
                  ↓
┌─────────────────────────────────────────────────────┐
│  RUNTIME (user session)                             │
│                                                     │
│  Adaptive Quiz (keep current engine)                │
│       ↓                                             │
│  User Vector (keep current construction)            │
│       ↓                                             │
│  Neural Matcher → probability per field             │
│  (replaces weighted arithmetic distance)            │
│       ↓                                             │
│  Top N fields → RAG query → real job requirements   │
│       ↓                                             │
│  Roadmap (gap from real job postings, not hardcoded)│
└─────────────────────────────────────────────────────┘
```

---

## State of the System

| Component | State |
|---|---|
| Question bank (1,702 Qs) | Done |
| Multi-label trait classification | Done (1,611 labeled rows) |
| Adaptive quiz engine (elimination) | Done |
| Skill vector computation | Done |
| Arithmetic role matching | Done (weak — needs replacement) |
| Roadmap generation | Done |
| LLM annotation pipeline | Built but **not run** — no output CSV |
| Neural matcher | Not built |
| Job ads scraper | Not built |
| RAG vector store | Not built |

---

## The Three Improvements

### 1. Job Ads Scraping → RAG

**What to scrape:** job title, description, requirements, tech stack, experience level, soft skills.

**Tooling:**
- `playwright` or `httpx` + `BeautifulSoup` — scraping
- `sentence-transformers` — embed each job posting
- `ChromaDB` (local) — vector store

**What the RAG gives you:**
- Real market-driven skill weights (replaces hardcoded `required_skills` in the DB)
- Dynamic roadmap steps grounded in real job postings ("5 actual job ads you're close to all require Docker")
- Adaptive question selection informed by which skills the market actually differentiates on

**Target volume:** ~500 postings per field × 16 fields = ~8,000 total postings.

---

### 2. Neural Network Matcher

Replaces the arithmetic distance in `backend/app.py:183–224`.

**Architecture:**

```
User Answers (adaptive quiz)
       ↓
Per-question normalized values (0–1)
       ↓
Aggregate by abstract label (40-dim vector)    ← uses question_bank_labeled.csv
       ↓
MLP (40 → 64 → 32 → 16)
       ↓
Softmax → P(field_i) for each of 16 canonical fields
       ↓
Top 3–5 fields with confidence scores
```

**Training data source:** `answer_questions_local.py` output.
Each row: `(question, expert_role, predicted_fields, field_scores_json)`.
Flip perspective: "expert in Frontend answered like this" → "user who answers like this → Frontend."

**Loss function:** Cross-entropy with soft targets from `field_scores_json`.

**Why not cosine distance of embeddings?** User behavior doesn't embed cleanly in the same space as job descriptions without a learned projection layer. The MLP learns that projection from data.

**Training data volume needed:** ~500–2,000 synthetic sessions — your annotation pipeline can generate this.

---

### 3. RAG Integration into Adaptive Questioning

After the warmup phase (first 3 questions), query the RAG with the partial user vector to find the closest job cluster. The skills most discriminating within that cluster become the highest-priority next questions — better than pure variance across all remaining roles.

---

## Build Order (Critical Path)

### Step 1 — Run the annotation pipeline (BLOCKING)

`answer_questions_local.py` must run with Ollama locally to produce `question_bank_answered_local.csv`.

Output schema per row:
- `expert_role`, `predicted_fields`, `field_scores_json`, `confidence`
- `model_answer`, `model_reasoning`, `model_name`, `prompt_version`
- `run_id`, `timestamp_utc`, `is_synthetic`, `error`

This is the **bottleneck** — no neural training can start without this file.

---

### Step 2 — Neural Matcher

Once annotation output exists:

1. Load `question_bank_answered_local.csv`
2. Build feature matrix: aggregate answers per abstract label → 40-dim vector per session
3. Build target matrix: `field_scores_json` → 16-dim soft probability vector
4. Train MLP with cross-entropy loss
5. Export model (ONNX or pickle)
6. Swap into `compute_results()` in `backend/app.py:183–224`

Files to create:
- `data/models/neural_matcher.py` — model definition + training script
- `data/models/neural_matcher.pkl` — saved model
- `backend/matching.py` — inference wrapper used by app.py

---

### Step 3 — Job Ads Scraper + RAG

Independently of Step 1–2 (can run in parallel):

1. Write scraper for job postings (LinkedIn/Indeed/RemoteOK)
2. Parse: title, description, requirements, skills, experience
3. Run LLM or regex skill extractor to normalize skill names to canonical taxonomy
4. Embed with `sentence-transformers/all-MiniLM-L6-v2`
5. Store in ChromaDB with metadata: `{field, title, company, skills[], embedding}`

Files to create:
- `data/scripts/scrape_job_ads.py`
- `data/scripts/build_rag.py`
- `data/data/job_ads_chroma/` — ChromaDB store

---

### Step 4 — RAG-Powered Roadmap

Replace the hardcoded `required_skills` lookup in `backend/app.py:227–360` with a ChromaDB query:

1. User selects a field
2. Query ChromaDB: top 20 job postings for that field
3. Extract skill frequency across those postings → real required skill weights
4. Compute gap: user skill vector vs. real market requirements
5. Return roadmap steps grounded in actual job market data

---

## Key Files Reference

| File | Role |
|---|---|
| `backend/app.py:42–112` | Skill vector computation |
| `backend/app.py:183–224` | Role matching (replace with neural) |
| `backend/app.py:227–360` | Roadmap generation (connect to RAG) |
| `backend/app.py:600–722` | Adaptive quiz engine |
| `data/scripts/answer_questions_local.py` | LLM annotation pipeline |
| `data/data/question_bank.csv` | Source questions |
| `data/data/question_bank_labeled.csv` | 40-label trait classification |
| `data/data/question_bank_answered_local.csv` | LLM annotation output (missing) |
| `data/data/annotation_failures.jsonl` | Annotation error log |

---

## Canonical Field Taxonomy (v1)

```
Frontend Development      Backend Development      Full Stack Development
Mobile Development        Data Analysis            Data Science
Machine Learning          AI Engineering           Cyber Security
DevOps                    QA / Software Testing    Game Development
UI / UX Design            Product Management       Technical Writing
Software Architecture
```

---

## Non-Negotiable Rules (from ADAPTIVE_QUESTIONNAIRE_INSTRUCTIONS.md)

- Do not train only on LLM-generated data
- Do not mix label naming conventions
- Do not change prompts/taxonomy/features without version bump
- Do not evaluate adaptive and fixed on different test sets
- Do not deploy adaptive policy without offline simulation evidence
- Do not ignore failure rows or parsing errors

---

## Milestones

| # | Milestone | Depends on |
|---|---|---|
| M1 | Annotation pipeline produces valid output (≥99% parse success) | Ollama running locally |
| M2 | Neural matcher trained, offline metrics tracked (Precision@3, Recall@5, NDCG@5) | M1 |
| M3 | Neural matcher swapped into app.py, A/B vs. arithmetic baseline | M2 |
| M4 | Job ads scraped, RAG built (ChromaDB), 8,000+ postings | Independent |
| M5 | Roadmap generation pulling from RAG instead of hardcoded DB | M4 |
| M6 | RAG-informed adaptive question selection in warmup-exit phase | M2 + M4 |
