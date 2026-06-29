# Roadmap Enrichment Module — How It Works

This document explains the design of the **field-level requirement enrichment** layer
being added to the roadmap module. It is an explanation of how the module will work — no
code is being written yet.

## Why this module exists

Today the roadmap module serves a **hardcoded "basic" roadmap per field**
(`backend/app/data/roadmaps.json`, mirrored in `frontend/src/data.js`). The per-user
personalization step (`roadmap_service.get_roadmap` → OpenAI) generates a roadmap from the
career title + the user's `profile` + `missing_skills`. It is **not grounded in real market
demand**, and it doesn't even read the basic roadmap.

This module inserts a **precomputed, field-level enrichment layer** between the basic
roadmap and per-user personalization. It mines the job ads already in our pipeline to learn,
per field:

- which skills ads **require** beyond what the basic roadmap teaches, and
- which skills ads list as an **advantage** (nice-to-have).

Both are merged into an **enriched roadmap per field**. This is computed **offline, once per
field** — never per user request. Personalization then reads the enriched roadmap instead of
the raw basic one.

## Design decisions (made with the user)

| Decision | Choice | Why |
|---|---|---|
| How to split required vs advantage skills | **Hybrid** — rule-based section parsing + existing regex extractor, with a local-LLM fallback only when rules find nothing | The data has no required/advantage split; rules are free and fast over 1,575 ads, LLM only fills gaps |
| Where the offline job reads ads from | **Raw JSON flat files** (`data/jobs/raw/*.json`) | Same input `extract_skills.py` already uses; full description text available; no ChromaDB query vectors needed |
| How strict skill naming is | **Normalize, don't restrict** | Canonicalize every skill; reuse the roadmap's name when it matches a node, otherwise keep the canonical token so new market skills can surface |

## Key facts about the existing data (constraints)

1. **Field tags already exist** at every layer (raw JSON, Postgres `job_postings.field`,
   ChromaDB metadata), from the 16-field taxonomy in `data/config/field_taxonomy.json`. The 6
   careers' `field` values in `backend/app/data/careers.json` are an exact-string subset, so
   ads can be grouped by field directly. **Caveat:** the tag is a weak scrape-time keyword
   guess and sometimes mistags ads — the 0.15 inclusion threshold downstream suppresses most
   of that noise. Only 6 of 16 fields are reachable from the career taxonomy.
2. **No required-vs-advantage split exists.** The structured `skills` array (raw JSON +
   Postgres `jsonb`) is **flat**. The only place the distinction lives is the free-text
   `description`. So extraction must parse the description text.
3. **Three unrelated skill vocabularies, no shared keys:** roadmap node `id`(kebab)/`label`
   (free text); career `keySkills` (Title-case); job-ad `skills` (lowercased regex tokens). A
   bridging/alias map is needed to "reuse roadmap naming."
4. **A reusable extractor already exists:** `data/scripts/extract_skills.py` does ~160 regex
   patterns + `data/config/skill_aliases.json` normalization + an optional local **Ollama**
   LLM path + per-field default skill lists. The module reuses it instead of building a new one.

## How the module works, end to end

The module is a chain of **offline batch steps** added to the existing pipeline. Nothing runs
at request time except the final read by the personalization step.

```
scrape_job_ads.py
   ↓
extract_skills.py
   ↓
[NEW] extract_requirements.py   ── Phase 1: per-ad {field, required, advantage}
   ↓
[NEW] aggregate_requirements.py ── Phase 2: per-field required_pct / advantage_pct
   ↓
[NEW] build_enriched_roadmaps   ── Phase 3: merge into one enriched roadmap per field
   ↓
roadmap_service.get_roadmap     ── Phase 4: personalization reads the enriched roadmap
   ↓
build_rag.py (unchanged, parallel branch that builds ChromaDB)
```

### Phase 1 — Per-ad requirement extraction

Reads `data/jobs/raw/*.json`, processes each ad, writes a new artifact. Per ad:

1. **Section split (rules).** Parse the `description` into a `requirement` bucket and an
   `advantage` bucket using configurable cue keywords (new `data/config/requirement_cues.json`,
   not inline):
   - *Requirement cues:* "requirements", "required", "must have", "qualifications",
     "what you'll need", "essential", "mandatory", …
   - *Advantage cues:* "nice to have", "advantage", "bonus", "preferred", "a plus",
     "good to have", "desirable", …
   If no requirement section is found, the whole description is treated as the requirement
   context (advantage stays empty).
2. **Extract skills per bucket.** Reuse `extract_skills.py`'s matcher (regex + aliases) on the
   requirement text and the advantage text **separately**. (Light refactor: expose a pure
   `extract_skills(text) -> list[str]`; CLI behavior unchanged.)
3. **LLM fallback (hybrid).** Only when rules yield no skills in either bucket, call the
   existing local Ollama path to emit `{required_skills, advantage_skills}`. Local + free.
4. **Normalize, don't restrict.** Canonicalize each token via `skill_aliases.json`; if it
   matches a roadmap node (by normalized `id`/`label`, read from `roadmaps.json`), substitute
   the roadmap node id; otherwise keep the canonical token.
5. **Field** is copied from the ad as-is (no re-validation in v1).

**Output schema** (`data/jobs/requirements/requirements.json`, one record per ad):

```json
{
  "id": "remoteok_1131911",
  "field": "Frontend Development",
  "required_skills": ["react", "typescript", "css"],
  "advantage_skills": ["graphql", "testing"],
  "extraction_method": "rules"
}
```

- `required_skills` / `advantage_skills` — canonical tokens; roadmap-matched ones carry the
  node id (e.g. `react`), off-roadmap ones keep their token (e.g. `kubernetes`).
- `extraction_method` — `"rules"` | `"llm"` | `"rules+llm"` for QA / fallback-rate tracking.

### Phase 2 — Field-level aggregation

Reads `requirements.json`, groups by `field`, and for each field computes:

- `required_pct[skill] = (# ads requiring skill) / (total ads in field)`
- `advantage_pct[skill] = (# ads listing skill as advantage) / (total ads in field)`

Output: a per-field stats artifact. Offline; runs after Phase 1, not at request time.

### Phase 3 — Merge into enriched roadmap (per field)

For each field, starting from the basic roadmap:

- `missing_required` = required skills that are **not already a roadmap node**.
- Include a missing skill only if `required_pct >= REQUIRED_PCT_THRESHOLD` (configurable
  constant = **0.15**, not hardcoded inline). Add each as a roadmap node tagged with its
  `required_pct`.
- Add advantage skills (not in the basic roadmap and not in `missing_required`) as a separate
  **"advantage" section**, each tagged with its `advantage_pct`.

Output: **one enriched roadmap per field**, stored/cached — not regenerated per user.

### Phase 4 — Wire into personalization

Swap the source that `roadmap_service.get_roadmap` reads (the
`load_roadmaps().get(career_id)` seam) from the basic roadmap to the enriched roadmap, and
feed it into `_build_prompt`/`_generate` so the LLM personalizes the enriched roadmap rather
than inventing one. Personalization logic itself is left unchanged unless it breaks.

## What does NOT change

- Auth, the questionnaire, and the matcher's nearest-neighbor logic are untouched.
- The request-time path stays the same — all enrichment is precomputed offline.
- `backend/app/data/roadmaps.json` and `frontend/src/data.js` `ROADMAPS` must stay in sync if
  either is edited.

## How to verify (Phase 1)

- Run the extractor (rules-only first) over `data/jobs/raw/*.json`; confirm `requirements.json`
  has one record per ad in the schema above.
- Spot-check 5–10 records per reachable field — do required/advantage buckets look right?
- Print stats: total ads, `extraction_method` distribution (how often LLM fired), and ads
  still empty after both passes.
- Confirm roadmap-matched tokens carry the node id while off-roadmap skills are retained.
- Re-run `extract_skills.py` CLI to confirm the refactor didn't change its output.
