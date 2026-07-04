# Matching Module Rework — Execution Plan (Prototype, Synthetic Labels)

Rework `backend/app/services/matching_service.py` from the fixed linear blend
(`FORMULA_WEIGHTS`: 0.40 questionnaire_fit + 0.40 semantic_similarity + 0.20 skill_overlap)
into a **learned matcher**. The three RAG signals don't disappear — they become input
features to a model that learns how to combine them from labeled data.

**Scope decisions (revised 2026-07-04):**

- **Supervision signal — synthetic silver labels.** Real domain experts are not
  available at this stage. Profiles are labeled by a **local LLM acting as a panel of
  synthetic career-expert personas**. These are *silver labels*: useful for building
  and validating the ML pipeline, but **not expert ground truth**. Every artifact,
  metric, and claim downstream must carry that qualifier.
- **Labeling pool:** real questionnaire submissions already persisted in
  `public.submissions` (`answers` jsonb), exported and anonymized.
- **Goal:** build and validate the end-to-end pipeline (dataset → baselines → model →
  serving with fallback) for the prototype. **Not** to claim expert-level
  recommendation quality — that requires the gold-label migration path at the bottom
  of this document.
- **Expected silver-label scale for v1:** ~200–1000 profiles (LLM labeling makes
  volume cheap; consensus filtering will shrink the usable set).
- **Manual free-text field:** deferred to v1.1. It doesn't exist in the product today
  (answers are strictly `{qId: 0–3|null}`), so v1 trains on questionnaire + RAG
  signals only.

**Engineering intent preserved from the original plan:** reproducible dataset, one
preprocessing module shared between training and serving, baselines before models,
a learned model ships only if it beats the current formula, explainability is a
ship-blocker, and serving always falls back safely to the current formula.

---

## Phase 0 — Synthetic labeling (LLM panel) & silver ground truth

The labeling pool exists: export and anonymize `answers` from `public.submissions`.
Reuse the existing local-LLM scripts under `data/scripts/`
(`answer_questions_local.py`, `labeling_pipeline.py`, `validate_synthetic_output.py`,
`quick_trust_check_local.py`) rather than building from scratch.

1. **LLM panel protocol** — each profile is labeled independently by **3–5 synthetic
   expert personas** (e.g. "senior engineering hiring manager," "career counselor,"
   "bootcamp instructor"), each with its own system prompt. Per persona, per profile,
   record:
   - `top1_career` (required, one of the 6 catalog ids)
   - `top2_career` (optional)
   - `confidence` (0–1 self-reported)
   - `explanation` (1–2 sentences — kept for auditing, not used as a feature)
   - metadata: `model_name`, `prompt_version`, `temperature`, `persona_id`,
     `label_source: "synthetic_llm"`, timestamp.
   Pin the model and prompt version for a labeling run; a prompt change is a new
   `prompt_version` and labels from different versions are never silently mixed.
2. **Synthetic archetypes** — each persona also answers the questionnaire once per
   career as the ideal candidate (6 careers × N personas). Same metadata schema.
   These seed the metric-learning path and act as sanity anchors — and, like the
   labels, they are synthetic, not expert-authored.
3. **Synthetic agreement, not human agreement** — compute **Fleiss' κ across the
   panel** (plus pairwise Cohen's κ per persona pair). This measures **consistency
   between LLM personas**, which is *not* the same thing as human inter-expert
   agreement: personas sharing one base model can agree confidently and still all be
   wrong. Report it as *synthetic agreement* everywhere; never present it as an
   expert noise ceiling.
4. **Consensus filtering** —
   - **High-consensus** profiles (e.g. ≥ majority of personas agree on top-1) →
     training set.
   - **Low-agreement** profiles → `data/training/ambiguous_labels.parquet`, excluded
     from training but kept: they are the highest-value candidates for future human
     labeling, and a useful hard-case eval slice.
5. **Manual sanity check** — a human (you) reviews ~30 labeled profiles across the
   consensus spectrum: do the labels and explanations look reasonable? Is any career
   systematically over-assigned? This is not expert validation — it's a smoke test
   against obvious LLM failure modes (position bias, one persona dominating, a
   career the model never picks).

**Deliverables:**
- `data/training/silver_labels.parquet` — per-profile consensus label + per-persona
  votes + full metadata
- `data/training/archetypes_synthetic.parquet`
- `data/training/ambiguous_labels.parquet`
- `data/training/synthetic_agreement_report.md` — κ numbers, label distribution,
  sanity-check notes, model/prompt versions
- *(future, initially absent)* `data/training/gold_labels.parquet` — reserved for
  real expert labels; same schema with `label_source: "human_expert"`.

**Gate 0 — pass only if all three hold:**
1. Synthetic agreement is acceptable (personas mostly converge; if κ is very low the
   prompts/personas are broken, and if it is suspiciously near-perfect the personas
   are probably not independent — investigate either extreme).
2. Label distribution over the 6 careers is plausible (no career at ~0%, no career
   dominating far beyond what the submission pool suggests).
3. The manual sanity check passes.

## Phase 1 — Dataset builder (feature pipeline)

New script `data/scripts/build_training_set.py`, **consuming
`data/training/silver_labels.parquet`** (high-consensus rows only):

- Per labeled profile, replay through the existing pipeline
  (`CareerRepository.get_candidates` logic, offline) to get
  **semantic_similarity ×6** and **skill_overlap ×6**; compute the current
  **questionnaire_fit ×6** as a prior feature.
- Add **q1–qN raw ordinals + N presence masks** (branched-away q3/q9 → mask=0).
  Don't pre-collapse ordinals with the old weights. (Originally 10 questions → 38-dim
  vector; DEV-29 grew the bank to 13 → features-v2, 44-dim. The question count is
  derived from `questions.json`, never hardcoded.)
- Carry `label_source` and `prompt_version` through as dataset metadata columns, so
  silver- and future gold-labeled rows can be distinguished, weighted, or split at
  training time without rebuilding.
- **Pin the ChromaDB snapshot** — record the store build date/hash in dataset
  metadata. Train and serve must use the same store generation.

**Deliverable:** one reproducible feature table + a preprocessing module **shared
verbatim between training and serving** (lives in `backend/app/services/`; the
training script imports it from there).

## Phase 2 — Baselines (the bar to clear)

Four scorers evaluated identically with **stratified 5-fold CV**:

1. **Current formula** (`FORMULA_WEIGHTS` blend) — the incumbent.
2. **Logistic regression** on the feature table.
3. **LightGBM** on the feature table.
4. **Zero-train archetype nearest-neighbor** — cosine from the user's structured
   vector to each synthetic archetype.

**Metrics:** top-1 / top-2 / top-3 accuracy; MRR/NDCG against panel top-2 rankings;
reliability curve for calibration. Script: `data/scripts/evaluate_matchers.py`
producing one comparison table.

**Framing rule for all Phase 2+ results:** every metric is **agreement with the
synthetic LLM panel**, not expert-validated accuracy. Reports, the README, and any
demo must say "top-2 agreement with synthetic labels," never "92% accurate." A model
that beats the formula here has learned to predict the panel — which is the correct
prototype milestone, and nothing more.

**Gate 1:** if nothing beats the current formula by a meaningful margin on the silver
set, the rework stops here — publish the numbers and revisit when labels improve.
That outcome is a success (a cheap, honest answer), not a failure. Note the
double-synthetic caveat: if the LLM panel happens to reason like the hand-authored
weights, the formula will look artificially strong (or the learned model's win
artificially easy). The agreement report should include formula-vs-panel agreement to
size this effect.

## Phase 3 — Learned models *(prototype stage; only if Gate 1 passes)*

Two challengers against the Phase-2 LightGBM:

- **3a. Tuned GBT** — class weights for imbalance, early stopping, light
  hyperparameter search. Probable winner at this scale; feature importances come
  free for explainability.
- **3b. Small NN** — `38 → 64 → 32 → 6`, soft-target cross-entropy using the panel's
  top-2 votes (the vote distribution is a natural soft target), dropout + weight
  decay + early stopping.
- **3c. Two-tower metric model** — user tower encodes the feature vector; career
  tower initialized from the synthetic archetypes; triplet/contrastive loss. Keep
  alive even if it loses on accuracy: it's the only path that admits a 7th career
  without retraining, and it transfers most gracefully when gold labels replace
  silver ones.

**Gate 2:** pick by held-out **top-2 agreement + calibration after temperature
scaling** on the silver set. Whatever wins, apply temperature scaling before scores
become `matchPercent` — with the explicit caveat that calibration against synthetic
labels is provisional and must be redone on gold labels (see migration path).

## Phase 4 — Explainability *(ship-blocker, not polish)*

- `score_breakdown` keeps the same three keys (`semantic_similarity`,
  `questionnaire_fit`, `skill_overlap`) — still computed as model inputs, surfaced as
  explanatory features. Zero frontend change.
- `reasons`: replace the threshold heuristics in `_reasons()` with attribution — SHAP
  for GBT (TreeSHAP is fast enough per request), integrated gradients if the NN wins.
  Map top attributed features to human sentences via a small template table keyed by
  question id.
- `matched_skills` / `missing_skills`: unchanged — they come from `_skill_signals()`,
  independent of the scorer.

## Phase 5 — Serving integration

- **Export:** ONNX (covers both GBT via `onnxmltools` and the NN) + the shared
  preprocessing module. Artifact path via new `MATCHER_MODEL_PATH` setting in
  `core/config.py`, default unset — **the prototype default is the current formula;
  the learned model is opt-in**.
- **Load once** in the `main.py` lifespan, same pattern as the embedding model +
  Chroma collection.
- `matching_service.match(answers, candidates)` **keeps its exact signature and
  response shape**. Model loaded → assemble features, run inference,
  temperature-scale, top-3; missing artifact or any inference error → **fall back to
  the current formula**, which stays in the file (`FORMULA_WEIGHTS` and all). Same
  defensive posture as the existing ChromaDB/Supabase fallbacks.
- **Provenance:** stamp served recommendations with `model_version` (including
  `label_source: synthetic` for silver-trained artifacts) in the `recommendations`
  jsonb already persisted to `submissions`, so cohorts are comparable retroactively
  and silver-trained output is never mistaken for expert-validated output later.
- **Tests:** existing suite must pass untouched with no model configured (formula
  path). Add: model path (tiny fixture artifact), fallback-on-error, and shape parity
  between the two paths. `FakeCareerRepository` already covers candidate injection.
- No `frontend/src/data.js` change — the client-side matcher remains the
  "backend is down" offline estimate.

## Phase 6 — v1.1 and the flywheel *(out of v1 scope)*

- **Free-text field:** frontend textarea + extend `QuestionnaireSubmission` with
  optional `about: str` + embed with the already-loaded MiniLM (`all-MiniLM-L6-v2`)
  → +384 dims (or a learned ~64-dim projection). Requires re-labeling (the panel
  should see the free-text too) and retraining.
- **Weak labels:** `selected_career` + `roadmap_progress` rows are implicit positives
  already being persisted — the first *human* signal in the system. Define a retrain
  cadence mixing silver labels with behavioral weak labels; as behavioral data grows
  it should progressively outweigh the synthetic panel.
- **Monitoring:** compare formula vs. model cohorts via the `model_version` stamp.

## Limitations (state these anywhere results are shown)

- **Synthetic labels encode LLM bias.** The panel personas share a base model and its
  priors about careers; agreement between them is consistency, not correctness.
  Systematic biases (e.g. steering certain answer patterns toward data science) will
  be learned faithfully by any model trained on them.
- **Evaluation on synthetic labels likely overestimates real-world quality.** All
  reported metrics measure agreement with the panel. Real users and real experts may
  disagree with the panel in ways these numbers cannot detect.
- **Circularity risk.** The features include the hand-authored `questionnaire_fit`
  prior, and the panel may reason similarly to those hand weights; parts of the
  pipeline can therefore validate each other without any external truth entering.
- **No reliability claim.** Until validated against real expert gold labels, the
  system should be described as a *prototype learned matcher trained on synthetic
  labels* — not as an expert-quality recommender. Displayed `matchPercent` values are
  provisional and calibrated only against the synthetic panel.

## Future migration path: silver → gold

Designed in from day one via `label_source` metadata:

1. **Collect gold labels** — when real experts become available, run the original
   protocol (top-1 + optional top-2, ≥2 experts on an overlap set, human Cohen's κ as
   the true noise ceiling) into `data/training/gold_labels.parquet`. Start with the
   `ambiguous_labels.parquet` profiles — they're where human judgment adds the most.
2. **Measure the silver-gold gap** — evaluate the silver-trained model against gold
   labels before retraining. This one number says how much the synthetic setup
   overestimated quality, and whether the silver labels were a reasonable proxy.
3. **Mix or replace** — retrain weighting gold ≫ silver (e.g. 1.0 vs. 0.2–0.3), or
   drop silver entirely once gold volume suffices. The Phase 1 dataset builder
   already supports this split without rework.
4. **Recalibrate** — redo temperature scaling on gold labels before the displayed
   `matchPercent` is presented as meaningful; update the `model_version` stamp so
   gold-validated cohorts are distinguishable.
5. Only after (2)–(4) may the product drop the prototype qualifier.

## Risks

- **Chroma drift between train and serve** — semantic/skill features shift when
  `build_rag.py` reruns. Evaluate the trained model against a re-built store before
  each refresh goes live.
- **Panel pseudo-agreement** — personas on one base model can converge for the wrong
  reasons; near-perfect κ is a red flag, not a green one. Vary temperature/prompts
  and check per-persona label distributions in the agreement report.
- **Consensus filtering shrinks the set** — if high-consensus rows fall well below
  ~200, prefer the metric-learning path (3c) over the 6-way heads, and consider
  loosening the consensus threshold with per-row confidence weights instead of hard
  filtering.
- **Leakage** — never let `selected_career` from the same session leak into v1
  training features; keep the LLM explanations out of the feature set.

## Sequencing

| Phase | Depends on | Rough effort |
|---|---|---|
| 0 LLM panel labeling + agreement report | local LLM setup | ~2–3 days (no expert calendar time — the upside of synthetic) |
| 1 Dataset builder | Phase 0 output | ~1–2 days |
| 2 Baselines + Gate 1 | Phase 1 | ~1–2 days |
| 3 Models + Gate 2 | Gate 1 pass | ~3–5 days |
| 4 Explainability | Phase 3 winner | ~1–2 days |
| 5 Serving + tests | Phase 4 | ~2–3 days |
| 6 Flywheel / free-text | v1 shipped | separate milestone |
| Gold migration | real experts available | separate milestone |

Unlike the expert-labeled version of this plan, nothing here is calendar-bound on
other people — the whole prototype loop is executable now. The trade is honesty of
the evaluation, which the limitations section and the `label_source` metadata are
there to keep visible.

---

## Execution log

### Phase 0 — COMPLETE, Gate 0 PASSED (2026-07-04)

Script: `data/scripts/panel_label_profiles.py` (resumable; local Ollama
`qwen2.5:7b-instruct`, 3 personas, ~10 min per full run).

**Deviation from plan:** `public.submissions` held only **7 real submissions**
(2 sessions, 2 duplicates) — not the assumed 200–1000 pool. Filled with 200
generated synthetic profiles (30% career-seeded + noise, 30% two-career blends,
40% uniform random; adaptive q3/q9 branching respected; ~5% skips), tagged
`profile_source: real|synthetic`. The training pool is therefore synthetic profiles
with synthetic labels; the 7 real profiles ride along as a sanity slice.

**Iteration 1 (`panel-v1.0.1`) FAILED Gate 0:** Fleiss κ 0.930 (personas were
clones — one base model, single temperature 0.2), ux-designer 0% / product-manager
2.9% (developer-role default bias). Logs archived as
`data/training/panel_votes_v1.0.1.jsonl`.

**Iteration 2 (`panel-v1.1.0`) PASSED:** per-persona temperatures (0.2/0.6/0.9) +
equal-validity instruction for non-coding careers.

| metric | v1.0.1 | v1.1.0 |
|---|---|---|
| Fleiss κ | 0.930 | 0.864 |
| silver / ambiguous | 206 / 1 | 205 / 2 |
| ux-designer share | 0.0% | 17.6% |
| product-manager share | 2.9% | 6.8% |
| formula-vs-panel top-1 agreement | 34.5% | 43.4% |
| top-2 fill rate | ~0 | 100% |

Label distribution (v1.1.0): backend 50, data-science 50, devops 38, ux-designer 36,
frontend 17, product-manager 14.

Notable: the hand-authored `questionnaire_fit` heuristic labels **all 7 real
profiles devops**, while the panel differentiates (backend/devops/data-science) —
either a formula devops bias or a panel artifact; Phase 2 will quantify.

Deliverables written to `data/training/`: `silver_labels.parquet`,
`ambiguous_labels.parquet`, `archetypes_synthetic.parquet`,
`synthetic_agreement_report.md`, `real_profiles.json`, raw vote logs.

Known weaknesses carried forward: κ still high (shared base model — personas are
correlated, not independent raters); confidence nearly constant (~0.8, weakly
informative — do not use as a feature); class imbalance (PM 14, frontend 17 → class
weights required in Phase 2/3).

### Phase 1 — COMPLETE (2026-07-04)

- **Shared preprocessing module:** `backend/app/services/feature_builder.py`
  (`FEATURE_VERSION = "features-v2"` after DEV-29, 44 dims: 13 ordinals + 13 presence
  masks + 6 fit + 6 semantic + 6 skill-overlap; `QUESTION_IDS` derives from
  `questions.json`, career order = careers.json order). Unit
  tests in `backend/app/tests/test_feature_builder.py`, including a guard that
  `feature_builder.raw_fit` stays identical to `matching_service._raw_fit`.
  Backend suite: **61 passed** (55 existing + 6 new).
- **Dataset builder:** `data/scripts/build_training_set.py` replays each silver
  profile through the real serving path (build_profile -> MiniLM encode -> ChromaDB
  query per career -> feature_builder). Runtime ~5 s for 205 rows.
- **Outputs:** `data/training/train_features.parquet` (205 x 38 + labels/provenance),
  `data/training/dataset_metadata.json` (feature version, feature names, Chroma
  snapshot pin: 1,575 docs, sqlite size/mtime, embed model, rag_top_k).
- **Validation:** 0 NaNs; all signal families carry variance (fit std 0.13-0.31,
  semantic std 0.05-0.09, skill-overlap std 0.04-0.13). Market skills are
  ChromaDB-only in this run (Supabase unset — matches default serving config);
  recorded in metadata.

### Phase 2 — COMPLETE, Gate 1 PASSED (2026-07-04)

Script: `data/scripts/evaluate_matchers.py`; report:
`data/training/baseline_evaluation.md`. Stratified 5-fold CV, pooled out-of-fold
metrics, class-balanced training. **All numbers are agreement with the synthetic
panel, not expert-validated accuracy.**

| scorer | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE |
|---|---|---|---|---|---|---|
| formula (production) | 0.439 | 0.668 | 0.829 | 0.646 | 0.389 | 0.119* |
| archetype_nn (zero-train) | 0.327 | 0.595 | 0.824 | 0.575 | 0.335 | 0.135* |
| logistic (balanced) | **0.756** | **0.932** | 0.971 | 0.864 | **0.723** | **0.103** |
| lightgbm (balanced) | **0.761** | 0.927 | 0.971 | **0.866** | 0.696 | 0.168 |

*pseudo-probability ECE (softmax over scores), directional only.

**Gate 1: PASSED** — best learned top-2 0.932 vs formula 0.668 (margin +0.263,
threshold +0.05). Logistic and LightGBM are effectively tied; both go to Phase 3.

**Product-relevant finding (silver-label caveat applies):** on this pool the
production formula has per-class top-1 recall devops 0.97, backend 0.00,
product-manager 0.00 — it almost always ranks devops first and never backend/PM.
This matches the Phase 0 observation (all 7 real profiles → devops by the formula)
and suggests the hand weights have a devops skew worth checking independently of
this rework.

**Archetype takeaway:** panel archetypes alone are the weakest scorer — they stay
as an auxiliary signal (Phase 3c initialization), not a standalone path.

### Phase 3 — COMPLETE, Gate 2 PASSED (2026-07-04)

Script: `data/scripts/train_models.py`; report: `data/training/model_selection.md`;
winner config: `data/training/gate2_winner.json`. Same outer 5-fold protocol as
Phase 2; GBT/logistic tuned by nested inner 3-fold CV; NN uses soft targets from
the panel vote distribution (top1=1.0, top2=0.4); two-tower career tower is
initialized from mean panel archetypes.

| model | top-1 | top-2 | top-3 | MRR | balanced | ECE raw | ECE scaled | T |
|---|---|---|---|---|---|---|---|---|
| **logistic_tuned (winner)** | **0.776** | **0.937** | **0.976** | **0.875** | **0.734** | **0.065** | 0.086 | 0.85 |
| gbt_tuned | 0.756 | 0.902 | 0.971 | 0.859 | 0.707 | 0.186 | 0.051 | 2.60 |
| small_nn (soft targets) | 0.722 | 0.922 | 0.976 | 0.846 | 0.706 | 0.199 | 0.075 | 0.45 |
| two_tower (archetype-seeded) | 0.629 | 0.834 | 0.922 | 0.780 | 0.598 | 0.062 | 0.060 | 1.15 |

**Gate 2 winner: `logistic_tuned`** (top-2 0.937 vs formula 0.668). Exactly the
outcome the plan predicted at this data scale: the simplest learned model wins and
the NN does not justify itself — ship logistic, keep NN/two-tower as future work.

Serving decisions locked here:
- **No temperature scaling for the shipped artifact.** Logistic's raw probabilities
  are already the best-calibrated (ECE 0.065); NLL-fitted T=0.85 *worsened* ECE.
  Recalibrate only when gold labels exist.
- small_nn had the best product-manager recall (0.71) — the weakest class for
  everyone; worth revisiting if PM labels grow.
- two_tower stays the documented path for adding a 7th career without retraining.

### Phase 4 — COMPLETE (2026-07-04)

Because the winner is linear, attribution is exact (coef × scaled value, centered
across classes) — no SHAP dependency added.

- **`backend/app/services/matcher_model.py`** — dependency-free artifact loader +
  inference (stdlib math only; no sklearn/pickle at serve time). Validates
  `feature_version` against `feature_builder.FEATURE_VERSION` on load and refuses
  mismatched artifacts. `predict_proba()` + `contributions()`.
- **`backend/app/services/reason_builder.py`** — maps attributions to the existing
  `reasons` shape: same-career fit/sem/skill sentences gated by their attribution,
  plus up to 2 question-level sentences quoting the user's own answer text
  (template per question id). Cross-career coefficients never surface (honest but
  unreadable). Falls back to the current default sentence when nothing clears the
  0.05 attribution floor.
- **`data/scripts/export_model.py`** — selects C by 5-fold CV (chose C=0.05,
  CV top-2 0.946), trains on all 205 rows, writes
  `data/models/matcher_logistic_v1.json` (11 KB JSON: scaler stats + 6×38 coefs +
  provenance incl. label_source=synthetic_llm, Chroma snapshot, prompt versions).
- **Tests:** 10 new in `test_matcher_model.py` — suite now **71 passed**.
- **Demo (real artifact, real profiles):** top-1 matched the panel label on all
  three spot-checked profiles; reasons quote the driving answers (e.g. ux-designer
  92% ← "visual design is my happy place").
- **Known UX quirk for later polish:** attribution can truthfully cite a
  "negative-sounding" answer as a positive driver (e.g. "Never tried coding" →
  devops). Consider filtering option-value-0 quotes in a UI pass.
- `score_breakdown` and `matched_skills`/`missing_skills` are untouched — they
  keep coming from the existing signal computations (wired in Phase 5).

### Phase 5 — COMPLETE (2026-07-04) — v1 rework DONE

- **Config:** `matcher_model_path` in `core/config.py` (`MATCHER_MODEL_PATH` env,
  default empty = formula; documented in `backend/.env.example`). Relative paths
  resolve against the uvicorn cwd (`backend/`), so use
  `../data/models/matcher_logistic_v1.json`.
- **Lifespan:** `main.py` loads the artifact once at startup next to the RAG
  loader; a bad/missing artifact logs a warning and the app serves the formula.
- **`matching_service.match(answers, candidates, model=None)`** — same signature
  plus optional model. Model path: features via the shared `feature_builder`,
  probabilities → `matchPercent`/`score` (top-3, deterministic tie-break),
  attribution reasons via `reason_builder`; `score_breakdown` and
  `matched_skills`/`missing_skills` computed exactly as before. Any model
  exception → log + formula fallback. `FORMULA_WEIGHTS` and the full formula path
  remain in the file.
- **Provenance:** every recommendation now carries `model_version`
  (`formula-v1` or the artifact version). It flows into the persisted
  `recommendations` jsonb via the existing `save_submission`, so silver-model
  cohorts stay distinguishable. Pydantic default keeps old persisted rows valid.
- **Tests:** 6 new in `test_matching_with_model.py` (model ranking + version
  stamp, shape parity between paths, broken-model fallback, no-model == formula,
  missing market data, dedupe). Suite: **77 passed**; all pre-existing tests
  untouched and green with no model configured.
- **E2E verified live:** uvicorn with `MATCHER_MODEL_PATH` set logs
  "Learned matcher loaded: matcher-logistic-v1 (label_source=synthetic_llm)";
  POST /api/questionnaire/submit returned model-scored recommendations
  (data-science 48% with quoted-answer reasons) with `model_version:
  matcher-logistic-v1`. Same request with a bad path fell back to formula output
  (`model_version: formula-v1`) after a logged warning — fallback confirmed live.
- **Calibration note honored:** artifact ships `temperature: 1.0` (raw
  probabilities; Gate 2 showed scaling hurt). Percentages are agreement-with-panel
  calibrated only — the Limitations section applies to anything user-facing.

**Remaining (v1.1+ / gold migration):** free-text feature, weak-label flywheel,
real expert labels + recalibration, frontend display of `model_version`/prototype
disclaimer if desired.
