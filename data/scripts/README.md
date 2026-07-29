# scripts/

All Python scripts for data collection, labeling, annotation, and validation. Run from the project root.

## Matcher training environment

The Phase 2/3 matcher scripts (`evaluate_matchers.py`, `train_models.py`,
`export_model.py`, and the shared `nn_model.py` they both import) run in a
virtualenv of **their own**, built from a hash-pinned lockfile:

```bash
python -m venv data/venv-training
data/venv-training/bin/python -m pip install --require-hashes -r data/requirements-training.txt
data/venv-training/bin/python data/scripts/evaluate_matchers.py
```

(Paths follow the repo's POSIX convention, as in root `CLAUDE.md`. On Windows,
`Scripts/` replaces `bin/` in every venv path on this page.)

Not `backend/venv` — that one runs the service test suites, so every install into
it is an opportunity to move `numpy` or `pandas` under `dataset_digest()`, which
hashes feature and label *content*. Not root `requirements.txt` either: root is
entirely unpinned (`numpy>=1.20.0`, `pandas>=2.0.0`), and nobody deploying the
services needs torch.

Three mechanisms, none of them substitutes for the others:

| mechanism | job |
|---|---|
| `data/requirements-training.txt` | **prevents** environment drift |
| `dataset_digest()` (`dataset_guards.py`) | **detects** it |
| `env_manifest.py`, embedded in every report and verdict | **attributes** a number to an environment |

The lockfile resolves for one platform and interpreter — it is a single-machine
reproduction guarantee, not a cross-platform one. See the header of
`requirements-training.in` for what that costs elsewhere.

To change a pin, edit `data/requirements-training.in`, recompile with the exact
command in its header (all three flags matter — a missing one silently yields a
different lockfile), then re-run `evaluate_matchers.py` and confirm the digest is
unmoved. If it moved, no number from that environment is comparable to recorded
history — re-pin rather than re-baseline silently.

`env_manifest.py` is stdlib-only and its tests run under the service-test venv,
which proves it adds no dependency to the scripts that import it:

```bash
backend/venv/bin/python -m pytest data/scripts/tests -q
```

`test_nn_model.py`, `test_cross_fitted_temperature.py` and
`test_residual_matcher.py` need torch, so all three skip whole there and run in the
training venv instead:

```bash
data/venv-training/bin/python -m pip install pytest   # test tooling, see below
data/venv-training/bin/python -m pytest data/scripts/tests -q
```

**pytest is deliberately not in `requirements-training.txt`.** The lockfile's job
is to make the numbers reproducible, and a test runner is not part of producing
them — pinning it would put an unrelated dependency tree (and its future
resolution) inside the guarantee that protects the dataset digest. It is installed
separately, and installing it moves none of the pinned packages (verified: numpy
2.4.6, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.8.0, lightgbm 4.6.0, torch
2.12.0 unchanged before and after).

### Reproduction record (DEV-87, 2026-07-27)

`evaluate_matchers.py` was run **before any manifest wiring existed**, on source
byte-identical to commit `00ca4af`. It reproduced
`dataset_digest 2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`
and the recorded Gate-1 metrics exactly (logistic ECE 0.034099440082920096 /
stability 0.637516702641587; lightgbm 0.128155228434309 / 0.5566450817144618) —
`baseline_evaluation.md` came back byte-identical apart from its `Generated:`
timestamp. The manifest was added only afterwards, and the run was repeated: same
digest, same metrics, and the report diff is exactly the added `## Environment`
section. The manifest touches report text and one additive JSON key; it enters no
computation.

`model_selection.md` / `gate2_winner.json` are wired for the manifest but **not
regenerated here**: the Gate-2 re-baseline is sequenced after the cross-fitted
temperature fix (plan Step 4.2, execution-order item 5), and re-running Phase 3
now would break the recorded Gate-2 numbers ahead of that deliberate break.

### Reproduction record (DEV-90, 2026-07-27)

Adding the neural matcher to the Gate-1 candidate list must change what is
*measured*, never what the measurement is computed on. It didn't:

- `dataset_digest` still
  `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`.
- `logistic` ECE `0.034099440082920096` / stability `0.637516702641587` and
  `lightgbm` `0.128155228434309` / `0.5566450817144618` reproduced to the last
  digit — the incumbents' entries in `gate1_verdict.json` are bit-identical to the
  DEV-87 run.
- `gate1_verdict.json` gained a `small_nn` entry under `metrics` and one additive
  top-level key, `reported_not_gated`. No key was removed or reshaped.

`small_nn` **qualified**: ECE 0.062 (floor 0.10), top-2 stability 0.615 (floor
0.60). That is the first time it has been scored by the gate at all rather than
asserted about in a Phase-3 report — but note it clears stability by 0.015, and it
is the *ranking* that is the product, so treat the margin as thin until the sweep
(execution-order item 6) reports seed variance around it. Qualified is also only
the first of the four states in `CONTEXT.md`: it says nothing about Selected,
Servable or Deployable.

Its reseeded stability — reported, never gated — is **0.667**, measured on the same
outer folds, inner resamples and test rows as the gated 0.615 so the two differ in
what varies and nothing else. Measuring it on the *full* outer training partition
instead reads 0.706, and that number is wrong to print beside the gated one: the
0.04 gap is partly the larger training set, not seed robustness. Nearly three times
the margin by which the model clears the floor.

`small_nn`'s Gate-**2** numbers in `model_selection.md` are now stale: sharing
`nn_model.py` re-seeds the network per fit, where the inline version inherited
accumulated process-global torch RNG state. They are re-baselined with the
cross-fitted temperature, not piecemeal.

### Reproduction record (DEV-91, 2026-07-28)

The cross-fitted-temperature fix and the one-time Gate-2 re-baseline. This is the
first record here where numbers are *supposed* to move, so it is split in two.

**Unmoved, verified rather than asserted.** `evaluate_matchers.py` was re-run on
unchanged code before the fix and reproduced everything to the last digit: digest
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`, `logistic`
ECE `0.034099440082920096` / stability `0.637516702641587`, `lightgbm`
`0.128155228434309` / `0.5566450817144618`, `small_nn` `0.061831` / `0.615315`,
reseeded `0.667016`. The regenerated report differed from the committed one by its
`Generated:` timestamp and nothing else. Gate 1 is unaffected **structurally**, not
just empirically: it gates on RAW ECE, has never applied a temperature, and
`evaluate_matchers.py` does not import `train_models.py` in either direction.

**Moved, deliberately.** Every Gate-2 `ece_scaled`/`temperature` in
`model_selection.md` and `gate2_winner.json`, per ADR 0004. All four models were
re-baselined in ONE run. Three results worth carrying forward:

- **`gbt_tuned` and `logistic_tuned` reproduce the old protocol exactly.** The new
  `ECE pooled-T (legacy)` column recomputes what the old code printed: 0.047 and
  0.103, matching the 2026-07-19 record, with pooled Phase-3 temperatures 1.65 and
  1.00 also matching. Their raw OOF is untouched, so their entire movement is the
  protocol. Their top-2 cannot move at all — temperature scaling is monotone within
  a row.
- **`small_nn`'s two causes are each ~0.023 and nearly cancel.** Recorded 0.101 ->
  legacy 0.078 is DEV-90's per-fit re-seeding alone; legacy 0.078 -> cross-fitted
  0.102 is DEV-91 alone. The net move from the recorded number is ~0.001.
  Attributing that net to cross-fitting would have been wrong in both magnitude and
  sign — the trap this ticket was warned about, and it materialised.
- **The bias has no reliable direction in either metric.** The guarantee is
  family-relative: a pooled temperature is the argmin of NLL on its own pool *among
  constant temperatures*, which is what makes the old number a fitted minimum
  rather than a measurement. Cross-fitting leaves that family — five per-fold
  constants absorb fold-specific miscalibration one constant cannot — so it can
  score lower, and here it does: cross-fitted ECE is lower for three of four models
  and cross-fitted NLL is lower for `logistic_tuned`. ADR 0004's "optimistic" is
  annotated accordingly. The decision is unaffected: the defect is that the number
  was never a held-out estimate, which holds whichever way it moves.

`two_tower` moved for a second reason of its own: it seeds from process-global torch
RNG rather than per fit (unlike `nn_model.NNClassifier`), so the three extra fits
per fold that cross-fitting inserts shift it. Reproducible from a clean run, but
order-dependent. Left as-is deliberately — making it deterministic would have been a
second uncontrolled change to a model's identity inside the run meant to
re-baseline it. Worth its own ticket.

`export_model.py` requires the Phase-3 calibration record rather than silently
defaulting, but does not transfer its temperature: `logistic_tuned` selected
heterogeneous Cs across folds, while the artifact serializes one fixed C. The
exporter therefore refits on pooled OOF predictions from the exact selected
configuration. On this dataset Phase 3 records **1.00**, while fixed `C=1.0`
reproduces **1.05**; the regenerated artifact now slightly softens served
`matchPercent` values through the DEV-88 inference path.

### Reproduction record (DEV-92, 2026-07-29)

The Residual Matcher (`nn_model.ResidualMatcher`, plan Step 2.3, ADR 0003). Adding
a model must not perturb the models already scored, and it didn't — **nothing moved
at all**, in either gate. Both re-runs were made from `data/venv-training` (the
hash-pinned stack of DEV-87; `Scripts/` on this Windows machine) on the final state
of the code, not an earlier one:

- `evaluate_matchers.py` re-run: `dataset_digest` still
  `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`; `logistic`
  ECE `0.034099440082920096` / stability `0.637516702641587`, `lightgbm`
  `0.128155228434309` / `0.5566450817144618`, `small_nn` `0.061831` / `0.615315`,
  reseeded `0.667016`. `gate1_verdict.json` and `baseline_evaluation.md` came back
  byte-identical apart from their timestamps, so the regenerated files were
  reverted rather than committed.
- `train_models.py` re-run: all four Gate-2 rows identical to the DEV-91
  re-baseline — `gbt_tuned` 0.892 / 0.040, `logistic_tuned` 0.849 / 0.061,
  `small_nn` 0.845 / 0.102, `two_tower` 0.763 / 0.081 (top-2 / cross-fitted ECE).
  `model_selection.md` and `gate2_winner.json` likewise differ only by timestamp
  and were reverted.

Three reasons that is worth stating rather than assuming, because two changes here
touched code that produced the recorded numbers:

- **`fit_logistic` now delegates to `nn_model.frozen_logistic`.** The Residual
  Matcher's paired-comparison argument rests on its frozen base being exactly the
  Incumbent's configuration, and a comment claiming so enforces nothing — so there
  is one construction site. The re-run is what shows the delegation is inert.
- **`NNClassifier.predict_proba`'s standardize-and-forward block moved into
  `_mlp_output`**, shared with `ResidualMatcher.predict_proba` so the two cannot
  hold drifting copies of a scaler contract fitted on training rows only. The
  arithmetic is unchanged, and `small_nn`'s two gate rows reproducing to the last
  digit is what shows it.
- **`two_tower` did not move, and that was arranged rather than lucky.** It seeds
  from process-global torch RNG rather than per fit, so its predictions depend on
  how many torch fits preceded them (DEV-91 documented this instead of fixing it).
  The Residual Matcher is deliberately **not** wired into `train_models.main()`, so
  no torch fit was inserted ahead of `two_tower` and its ordering is untouched.
  Whoever wires the sweep in must order it after `two_tower` or fix that seeding as
  a separate, separately-reported change.

Why it is not in `main()`: it is one of the fourteen Variants of the round-1 sweep
(execution-order item 6). Entering it in Gate 2 now would select its configuration
under a different protocol than the one every other Variant competes under. What
landed is the model plus the selection seam the sweep consumes —
`select_residual_config` (inherits the fold's tuned-logistic `C`, then grid-argmaxes
`alpha` on inner-CV top-2), `fit_residual`, and `alpha_zero_verdict`, which encodes
the pre-registered ">= 3 of 5 folds at alpha=0 means no non-linear signal found"
rule in one place so the sweep reads it rather than restating it.

**No `alpha` has been selected on the real data.** Nothing in this record is
evidence about whether a non-linear residual helps.

Test counts: `data/scripts/tests` is **41** under the training venv (was 23), and
**7 passed + 3 skipped** under `backend/venv` (was 7 + 2) — `test_residual_matcher.py`
is the third module that skips whole there, for the same reason as the other two:
no torch. The five service suites were re-run and are unchanged at **268**
(questionnaire 18, matching 108, roadmap 30, auth 31, history 81); no file under
`services/` is in this change.

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
