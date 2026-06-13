# Adaptive Questionnaire Implementation Instructions

## Goal
Build a production-ready adaptive questionnaire that:
- predicts the most suitable study fields for a user,
- returns a ranked list of 3-5 fields,
- asks fewer but more informative follow-up questions,
- is measurable, reproducible, and safe to iterate.

---

## Final Deliverable Definition
You are done when all items below are true:
- A trained recommender model accepts questionnaire answers and outputs top 3-5 fields with probabilities.
- An adaptive engine chooses the next best question based on current uncertainty.
- The system stops asking questions when confidence is high enough (or max question limit is reached).
- Offline evaluation proves adaptive performs better than fixed questionnaire on quality and efficiency.
- The full pipeline is reproducible from raw data to trained model and reports.

---

## Phase 1: Data Foundation (Must Do First)

### Step 1. Freeze a Field Taxonomy
Define the exact field labels the system can recommend (canonical list).

Rules:
- Use one canonical name per field (for example `QA`, not mixed `Quality Assurance` / `Software Testing`).
- Keep a mapping file for synonyms and aliases.
- Do not add new labels mid-training without versioning the taxonomy.

Canonical field list (v1):
- Frontend Development
- Backend Development
- Full Stack Development
- Mobile Development
- Data Analysis
- Data Science
- Machine Learning
- AI Engineering
- Cyber Security
- DevOps
- QA / Software Testing
- Game Development
- UI / UX Design
- Product Management
- Technical Writing
- Software Architecture

Output:
- `field_taxonomy.json` (canonical fields, aliases, version, date).

### Step 2. Validate Core Input Data
Use `data/data/question_bank.csv` as the question source of truth.

Rules:
- Required columns must exist and be non-empty where expected: `id`, `category`, `subcategory`, `question`, `answer_type`, `options`, `tags`.
- Question IDs must be unique.
- Invalid rows must be logged and excluded (never silently dropped).

Output:
- Data quality report (row counts, invalid rows, duplicates, missing fields).

### Step 3. Define ML-Ready Label Format
Create a stable target format for recommendations.

Rules:
- Support multi-label targets (user can match multiple fields).
- Store label confidence/probability where possible.
- Use a consistent schema across all training/evaluation runs.

Output:
- Label schema document and sample rows.

### Step 3A. Add Beginner Question Quality Gate
Before large-scale annotation, run quality checks focused on beginner-facing field detection.

Required checks:
- beginner-safe language (avoid unexplained jargon/acronyms),
- field discriminativeness (question helps separate fields),
- construct alignment with category/subcategory/tags,
- ambiguity/overlap/leading wording risk,
- answerability for inexperienced users,
- readability and length constraints.

Artifacts:
- `data/reports/beginner_field_question_quality_rubric.md`
- `data/scripts/audit_question_quality.py`
- `data/reports/question_bank_beginner_quality_flags.csv`
- `data/reports/question_revision_proposal.md`

Command:
- `python data/scripts/audit_question_quality.py`

---

## Phase 2: Structured LLM Annotation Pipeline

### Step 4. Upgrade `answer_questions_local.py` to Strict Structured Output
Current script should produce deterministic machine-parseable outputs.

Required output columns per row:
- `expert_role`
- `predicted_fields` (JSON list)
- `field_scores_json` (JSON dictionary field -> score)
- `confidence`
- `model_answer`
- `model_reasoning`
- `model_name`
- `prompt_version`
- `run_id`
- `timestamp_utc`
- `is_synthetic` (0 or 1)
- `error` (empty if success)

Rules:
- Model must return valid JSON only.
- On parse failure, retry with stricter prompt up to N times (recommended 2-3).
- Never discard failed rows; write them to a failure log.
- Temperature must stay low for consistency (recommended 0.0-0.3).

Output:
- `question_bank_answered_local.csv` with strict schema.
- `annotation_failures.jsonl`.

### Step 5. Persona/Expert Strategy (Use Carefully)
Use experts to diversify explanations, not to replace ground truth.

Rules:
- One row can have one primary expert in standard runs.
- Multi-expert generation (for augmentation) must be flagged `is_synthetic=1`.
- Keep synthetic data ratio conservative initially (recommended synthetic:real <= 1:1).
- Never treat unvalidated synthetic labels as gold truth.

Output:
- Persona config file (expert map and rules).

### Step 5A. Quick Local Trust-Check Stage (Before Full Runs)
Run a short sampled workflow to verify that local-model outputs are trustworthy before expensive generation.

Checks:
- JSON validity,
- schema adherence,
- predicted field and score constraints,
- target field consistency,
- confidence sanity,
- contradiction/format sanity.

Artifacts:
- `data/scripts/quick_trust_check_local.py`
- `data/scripts/QUICK_TRUST_CHECK_README.md`
- `data/reports/quick_trust_check_results.csv`
- `data/reports/quick_trust_check_report.md`

Command:
- `python data/scripts/quick_trust_check_local.py --sample-size 20 --timeout-s 60`

---

## Phase 3: Baseline Recommendation Model

### Step 6. Build Features from User Answers
Transform questionnaire responses into numeric model features.

Examples:
- Raw answer values (Likert 1-5, option encodings),
- Aggregates by category/subcategory,
- Optional trait-level summary features.

Rules:
- Feature generation must be deterministic and versioned.
- No leakage: do not include future answers or target-derived fields.

Output:
- Feature matrix generation script and saved feature schema.

### Step 7. Train Baseline Multi-Label Ranker
Start simple and reliable first.

Recommended first models:
- One-vs-rest logistic regression, or
- LightGBM / XGBoost multi-label approach.

Rules:
- Use fixed train/validation/test split with seed.
- Save model artifact and training config.
- Track metrics per field and overall.

Required metrics:
- `Precision@3`
- `Recall@5`
- `NDCG@5`
- calibration quality (optional but recommended)

Output:
- Baseline model report and saved model file.

### Step 7A. Add BERT Embeddings as Optional Feature Upgrade
Transform question text into dense vectors and test as additional features.

Recommended approach:
- Use a sentence embedding model (for example `sentence-transformers` family).
- Encode question text from `question_bank.csv` into fixed-size vectors.
- Join embedding features with baseline answer-derived/tabular features.

Rules:
- Treat embeddings as augmentation, not replacement for response features.
- Keep the same train/validation/test split used by baseline.
- Keep preprocessing deterministic and versioned.
- Accept this upgrade only if held-out metrics improve.

Evaluation rule (must pass):
- Compare Baseline vs Baseline+Embeddings on:
  - `Precision@3`
  - `Recall@5`
  - `NDCG@5`
- Keep embeddings only if improvements are consistent and not just noise.

Output:
- Embedding artifact file(s) and mapping to question IDs.
- Comparison report (`baseline_vs_embeddings_report.md`).

---

## Phase 4: Adaptive Questionnaire Engine

### Step 8. Define Adaptive Policy
Choose how to select the next question after each answer.

Recommended policy options:
- Uncertainty sampling (focus on top ambiguous fields),
- Expected information gain,
- Entropy reduction.

Rules:
- Keep a mandatory short core block of broad questions first.
- Adaptive stage starts only after core block.
- Avoid asking near-duplicate questions.
- Prefer semantically diverse next questions (embeddings can be used for diversity control).

Output:
- Policy specification (`adaptive_policy.md`) and parameter config.

### Step 9. Define Stopping Criteria
Stop when enough confidence is reached.

Recommended stop rules:
- Max questions reached (hard limit), OR
- Top-1 minus Top-2 probability margin above threshold for K consecutive steps.

Rules:
- Must always return top 3-5 recommendations.
- If confidence is low, include "needs more data" state.

Output:
- Stopping config with thresholds.

### Step 10. Offline Simulation Before Production
Run session simulations against historical/synthetic response sets.

Rules:
- Compare adaptive vs fixed questionnaire under the same data splits.
- Track both quality and question count.
- Adaptive must show measurable gain before rollout.

Evaluation targets:
- Equal or better recommendation quality,
- Fewer average questions,
- Acceptable confidence calibration.

Output:
- Simulation report and go/no-go decision.

---

## Phase 5: Productionization and Monitoring

### Step 11. Deploy with Safety Guardrails
Put runtime constraints around recommendations.

Rules:
- Always provide ranked fields with confidence values.
- Log every interaction step (question shown, answer, posterior update, final output).
- Keep model and prompt version in all logs.

Output:
- Runtime logging schema and monitoring dashboard requirements.

### Step 12. Continuous Improvement Loop
Use real user outcomes to improve models and question policy.

Rules:
- Retrain on schedule (for example monthly) with versioned datasets.
- Maintain champion/challenger evaluation.
- Any taxonomy change requires migration/version plan.

Output:
- Model lifecycle SOP (standard operating procedure).

---

## Non-Negotiable Rules
- Do not train only on LLM-generated data.
- Do not mix label naming conventions.
- Do not change prompts/taxonomy/features without version bump.
- Do not evaluate adaptive and fixed on different test sets.
- Do not deploy adaptive policy without offline simulation evidence.
- Do not ignore failure rows or parsing errors.

---

## Recommended Folder/Artifact Layout
- `data/data/question_bank.csv` (source questions)
- `data/data/question_bank_answered_local.csv` (structured LLM outputs)
- `data/data/annotation_failures.jsonl`
- `data/config/field_taxonomy.json`
- `data/config/expert_map.json`
- `data/config/adaptive_policy.json`
- `data/reports/data_quality_report.md`
- `data/reports/baseline_model_report.md`
- `data/reports/adaptive_simulation_report.md`

---

## Suggested Milestones
- M1: Taxonomy + data validation complete.
- M2: Structured LLM annotation pipeline stable (>= 99% parse success).
- M3: Baseline recommender with tracked ranking metrics.
- M4: Adaptive simulator beats fixed baseline in offline tests.
- M5: Controlled production launch with monitoring.

---

## Definition of Success
The system consistently recommends 3-5 suitable fields with clear confidence, asks fewer but smarter questions, and improves over time based on real user response data under versioned, reproducible workflows.
