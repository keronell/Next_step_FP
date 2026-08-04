# scripts/

All Python scripts for data collection, labeling, annotation, and validation. Run from the project root.

## Pipeline order

```
scrape_job_ads.py
      ↓
extract_skills.py
      ↓
build_rag.py  →  jobs/chroma/

labeling_pipeline.py  →  questions/question_bank_labeled.csv
      ↓
answer_questions_local.py  →  answers/question_bank_answered_local.csv
      ↓
validate_synthetic_output.py  →  reports/
quick_trust_check_local.py    →  reports/
```

---

## Job pipeline

### `scrape_job_ads.py`
Fetches job postings from free APIs (RemoteOK, Jobicy, Remotive, Arbeitnow, and others) and scores each against the 16 canonical fields in `config/field_taxonomy.json`.

```bash
python data/scripts/scrape_job_ads.py
python data/scripts/scrape_job_ads.py --sources remotive arbeitnow
python data/scripts/scrape_job_ads.py --max-per-field 200
```
Output: `jobs/raw/*.json`

### `extract_skills.py`
Reads raw job JSONs and adds a normalized `skills` list to each job via regex patterns + tag passthrough + optional LLM enrichment.

```bash
python data/scripts/extract_skills.py
python data/scripts/extract_skills.py --use-llm     # slower, richer
python data/scripts/extract_skills.py --sources remoteok
```
Output: updates `jobs/raw/*.json` in place.

### `build_rag.py`
Embeds every job posting with `sentence-transformers/all-MiniLM-L6-v2` and stores it in a ChromaDB vector database for RAG retrieval.

```bash
python data/scripts/build_rag.py
python data/scripts/build_rag.py --reset            # rebuild from scratch
python data/scripts/build_rag.py --stats-only
python data/scripts/build_rag.py --query "React TypeScript" --field "Frontend Development"
```
Output: `jobs/chroma/` (gitignored, regenerable)

---

## Labeling pipeline

### `labeling_pipeline.py`
Auto-assigns multi-labels to all questions in `questions/question_bank.csv` using the ontology in `config/label_ontology.json`. Achieves 100% coverage with ~5.5 labels per question on average.

```bash
python data/scripts/labeling_pipeline.py
python data/scripts/labeling_pipeline.py --use-embeddings
python data/scripts/labeling_pipeline.py \
    --input data/questions/question_bank.csv \
    --output data/questions/question_bank_labeled.csv \
    --ontology data/config/label_ontology.json \
    --threshold 0.3
```
Output: `questions/question_bank_labeled.csv`

### `create_visualizations.py`
Generates distribution charts from the labeled question bank.

```bash
python data/scripts/create_visualizations.py
```
Output: `visualizations/*.png`

### `verify_output.py`
Validates the labeled output for coverage and format correctness.

```bash
python data/scripts/verify_output.py
```

---

## Annotation

### `answer_questions_local.py`
Generates synthetic persona answers for all questions using a local Ollama model. Each field is answered by `PERSONAS_PER_FIELD` (default 3) independent personas at distinct temperatures (`PERSONA_TEMPERATURES`) to avoid same-base-model clone effects, mirroring `panel_label_profiles.py`'s panel design. `target_field` is never forced into the model's `predicted_fields` — confirmation is measured honestly, not injected.

```bash
python data/scripts/answer_questions_local.py                  # full run
python data/scripts/answer_questions_local.py --limit 50       # smoke test
python data/scripts/answer_questions_local.py --aggregate-only # recompute the agreement report only
# Requires Ollama running at localhost:11434
```
Output: `answers/question_bank_answered_local.csv`, `reports/question_bank_agreement_report.md`

### `pipeline.py`
Orchestrates the full annotation pipeline end-to-end.

```bash
python data/scripts/pipeline.py
```

---

## Validation & auditing

### `validate_synthetic_output.py`
Checks structural quality of the synthetic annotations: JSON parseability, field-score validity, confidence range, Likert score validity, error rate.

```bash
python data/scripts/validate_synthetic_output.py
```
Output: `reports/synthetic_output_validation_report.md` + `.json`

**Pass criteria:**
- `predicted_fields` JSON valid ≥ 99% of rows
- `field_scores_json` valid ≥ 99% of rows
- Non-empty `error` rows ≤ 1%

### `quick_trust_check_local.py`
Fast trust-check on a small sample — run this before committing to a full annotation run.

```bash
python data/scripts/quick_trust_check_local.py --sample-size 20
python data/scripts/quick_trust_check_local.py --sample-size 20 --skip-model-call  # dry run
python data/scripts/quick_trust_check_local.py --sample-size 20 --model qwen3:14b --timeout-s 90
```
Output: `reports/quick_trust_check_results.csv` + `reports/quick_trust_check_report.md`

**Suggested acceptance rule:** trust pass rate ≥ 90%, JSON/schema validity ≥ 95%, target-field consistency ≥ 85%.

### `audit_question_quality.py`
Audits the question bank for beginner-friendliness and quality flags.

```bash
python data/scripts/audit_question_quality.py
```
Output: `reports/question_bank_beginner_quality_*.{md,csv}`

---

## Reproduction records

### Reproduction record (DEV-89, 2026-08-04)

q11-q18 attribution rendering. **Nothing was retrained, re-exported or re-swept**;
`dataset_digest` is untouched at
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`, no file under
`data/training/` or `data/models/` was written, and `MATCHER_MODEL_PATH` was not
flipped. This ticket ships on its own branch off `main`, independent of DEV-23.

Deliverable: `services/matching/app/services/reason_builder.py` (phrases for q11-q18),
`services/matching/tests/test_reason_coverage.py`,
`services/matching/tests/reason_diagnostics.py`, and
`services/matching/tests/data/question_phrases_snapshot.json`.

#### The defect

`reason_builder.py`'s `QUESTION_PHRASES` covered q1-q10 **and was also the iteration
set** (`for qid in QUESTION_PHRASES`), so with an 18-question bank the attributions
for q11-q18 were computed by the matcher and then discarded before reaching users --
16 of 36 question features, 44% of the question-feature surface, and precisely the
pure discriminators (zero questionnaire weight, signal carried entirely by per-option
bonuses) a learned model leans on hardest.

#### The measurement, computed rather than quoted

```bash
cd services/matching && ../../backend/venv/Scripts/python tests/reason_diagnostics.py --seeds
cd services/matching && ../../backend/venv/Scripts/python tests/reason_diagnostics.py --fixture conftest
```

Artifact `matcher_logistic_v2.json` (`features-v4`, the only artifact the current
layout accepts), 200 answer sets x top-3 careers = 600 explanations, seed 20260803,
`show_if` honored so exactly one of q14-q17 is answered per respondent.

Renderable share of **explainable** attribution mass -- own-career `fit`/`sem`/`skill`
plus all question features, cross-career coefficients excluded as
honest-but-unreadable:

| phrase mapping | mean | min | < 0.99 | explanations |
|---|---|---|---|---|
| current (q1-q18) | **1.000** | **1.000** | 0 | 600 |
| pre-DEV-89 (q1-q10) | 0.572 | 0.000 | 592 | 600 |

**This denominator is WIDER than the question-only reading reported alongside DEV-99
(0.293) and the two are not interchangeable.** The AC's universe includes the three
own-career signals, which `reason_builder.py:57-66` does emit sentences for.

Stable at 1.000 across seeds 1-4 (pre-DEV-89: 0.554 / 0.566 / 0.561 / 0.571), under
the sparse `conftest` fixture (pre-DEV-89: 0.731), and with `show_if` ignored so all
18 are answered.

#### Judgement calls, each counted rather than argued

1. **Positive mass only** -- `reason_builder` renders only above `MIN_CONTRIBUTION`,
   so negative attribution is unrenderable for every feature in the bank or out of it.
2. **Renderable means "has a rendering path"**, not "survives the `MAX_REASONS` /
   `MAX_QUESTION_REASONS` budget" -- under a "survives" reading the >= 0.99 bar is
   unreachable by construction. Renderability is **probed by driving `build_reasons`**,
   not by reading `QUESTION_PHRASES`, so a phrased-but-unrenderable question (a
   `questions_by_id` miss, an out-of-range answer) still counts as lost.
3. **Answered questions only** -- an unseen question has no option to quote. Excluded
   mass: 0.106 (skill-rich fixture) / 0.277 (sparse `conftest`).
4. **The `skill` signal needs names to list** -- dropped from the universe when
   `matched_skills` is empty. Excluded mass: 0.000 / 0.001, and **symmetric** between
   the current and pre-DEV-89 mappings (0.001 vs 0.001), so it does not flatter the
   "before" gap.

Disclosure: `chromadb` is not installed in `backend/venv`, so `semantic_similarity` is
canned (same constraint DEV-99 disclosed). The default fixture gives every career
market demand for its own key skills; `--fixture conftest` runs the sparse fixture so
the size of that thumb is visible in the table above.

#### The safety property

DEV-89 changes reasons, **not scores**. Verified over 400 comparisons (200 answer sets
x formula path and model path): career ordering, `matchPercent` and `score` are
identical under the pre- and post-DEV-89 mappings, while the rendered reasons differ --
the top reason for the first answer set becomes a q15 sentence, one of the previously
discarded discriminators.

Suite: `services/matching` 90 -> **112 passed** (22 new). `questionnaire` 18,
`roadmap` 27, `history` 88 unchanged. `services/auth` has **3 pre-existing failures on
`main`** (`ModuleNotFoundError: No module named 'supabase_...'` in
`tests/test_admin_routes.py`), unrelated to this ticket and unchanged by it.
