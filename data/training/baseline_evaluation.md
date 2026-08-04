# Baseline Evaluation — Phase 2 / Gate 1 (reframed)

> **CAVEATS THAT TRAVEL WITH EVERY RESULT BELOW**
> - Silver labels are **bank-consistent, not independently validated**: the
> panel's stage-2 vote follows the answer key derived from careers.json bonuses
> ~94% of the time it speaks. In this dataset the labels agree with the
> questionnaire-only heuristic fit (the answer-key winner) **52.2%**
> of the time, and with the full production formula (fit+sem+skill) top-1
> **46.1%** of the time. Panel-agreement numbers measure
> fidelity to the hand-authored bonus table, nothing more — Gate 1 no longer uses them.
> - Floor-level class representation for game-dev (5 labels) — at or below the 5-label stratified-CV minimum; treat their predictions and metrics as low-confidence.
> - Over-represented classes: frontend (47/232 rows, 20%) (more than 2x the uniform share). class_weight='balanced' prevents amplification during training, but the label skew remains in the data.

Generated: 2026-07-27T20:48:05Z
Dataset: 232 rows ({'synthetic': 225, 'real': 7}), feature version `features-v4`,
labels `panel-v2.1.0`, Chroma snapshot 1853 docs.
Protocol: stratified 5-fold CV (seed 42); metrics on pooled out-of-fold
predictions. All three trained scorers use class_weight="balanced".

## Environment

Every number in this report is only comparable to runs from an equivalent
environment. `dataset_digest` hashes feature and label *content*, so a change to
any package below can move it — and if it moves, nothing here is comparable to
recorded history (see docs/dev-23-nn-rework-plan.md Step 1).

- Python: 3.14.0 (cpython) — `3.14.0 (tags/v3.14.0:ebf955d, Oct 7 2025, 10:15:03) [MSC v.1944 64 bit (AMD64)]`
- Platform: Windows-11-10.0.26200-SP0 (AMD64)

| package | version |
|---|---|
| joblib | 1.5.3 |
| lightgbm | 4.6.0 |
| numpy | 2.4.6 |
| pandas | 2.3.3 |
| pyarrow | 24.0.0 |
| scikit-learn | 1.8.0 |
| scipy | 1.18.0 |
| threadpoolctl | 3.6.0 |
| torch | 2.12.0 |

## Comparison (panel agreement is DESCRIPTIVE only — see caveat a)

| scorer | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE* | top-2 stability |
|---|---|---|---|---|---|---|---|
| formula (production) | 0.461 | 0.582 | 0.659 | 0.611 | 0.493 | 0.162 | 1.000** |
| archetype_nn (zero-train) | 0.099 | 0.250 | 0.353 | 0.284 | 0.102 | 0.133 | 1.000** |
| logistic (balanced) | 0.741 | 0.871 | 0.927 | 0.838 | 0.694 | 0.034 | 0.638 |
| lightgbm (balanced) | 0.789 | 0.871 | 0.914 | 0.858 | 0.744 | 0.128 | 0.557 |
| small_nn (balanced, hard labels) | 0.638 | 0.810 | 0.909 | 0.774 | 0.606 | 0.062 | 0.615 |

*ECE for `formula` and `archetype_nn` is computed on softmax-normalized scores
(pseudo-probabilities) — directional only. Trained models emit real probabilities.
**Static scorers involve no training, so resampling stability is 1.0 by construction.

`small_nn` is scored here on **hard labels**, like every other gate candidate, so
the comparison is like-for-like. The soft-target variant that trains on the panel's
vote distribution is a different objective and remains a Gate-2 challenger in
`train_models.py`; qualification earned here would not transfer to it, which is why
`export_model.py` revalidates the exact shipped configuration against these same
thresholds rather than inheriting a verdict.

## Class balance: label share vs predicted share (over-prediction check)

| career | label share | formula pred | logistic pred | lightgbm pred | small_nn pred |
|---|---|---|---|---|---|
| frontend | 20.3% | 6.0% | 19.8% | 22.0% | 16.8% |
| backend | 6.5% | 0.9% | 6.5% | 4.7% | 7.3% |
| data-science | 6.5% | 4.3% | 7.8% | 6.9% | 6.0% |
| devops | 7.8% | 6.9% | 8.2% | 8.2% | 8.2% |
| product-manager | 2.6% | 0.9% | 2.2% | 3.0% | 2.2% |
| ux-designer | 5.2% | 3.9% | 5.2% | 5.2% | 4.7% |
| fullstack | 5.6% | 26.3% | 5.6% | 6.5% | 6.0% |
| mobile | 3.4% | 5.2% | 3.4% | 3.9% | 5.6% |
| data-analyst | 7.3% | 14.2% | 6.9% | 6.9% | 8.2% |
| machine-learning | 6.5% | 6.0% | 6.0% | 6.0% | 6.9% |
| ai-engineer | 3.9% | 2.6% | 4.3% | 3.9% | 4.7% |
| cyber-security | 4.7% | 3.4% | 5.2% | 5.6% | 6.0% |
| qa-engineer | 6.9% | 1.7% | 6.5% | 6.9% | 5.6% |
| game-dev | 2.2% | 9.9% | 3.0% | 2.2% | 2.6% |
| technical-writer | 4.7% | 3.0% | 4.7% | 3.0% | 4.3% |
| software-architect | 6.0% | 4.7% | 4.7% | 5.2% | 4.7% |

## Per-class top-1 recall

### formula

| career | top-1 recall |
|---|---|
| frontend | 0.23 |
| backend | 0.07 |
| data-science | 0.47 |
| devops | 0.61 |
| product-manager | 0.17 |
| ux-designer | 0.67 |
| fullstack | 0.77 |
| mobile | 0.88 |
| data-analyst | 0.82 |
| machine-learning | 0.73 |
| ai-engineer | 0.67 |
| cyber-security | 0.45 |
| qa-engineer | 0.25 |
| game-dev | 0.40 |
| technical-writer | 0.27 |
| software-architect | 0.43 |
### archetype_nn

| career | top-1 recall |
|---|---|
| frontend | 0.02 |
| backend | 0.40 |
| data-science | 0.00 |
| devops | 0.11 |
| product-manager | 0.00 |
| ux-designer | 0.00 |
| fullstack | 0.31 |
| mobile | 0.00 |
| data-analyst | 0.29 |
| machine-learning | 0.07 |
| ai-engineer | 0.33 |
| cyber-security | 0.09 |
| qa-engineer | 0.00 |
| game-dev | 0.00 |
| technical-writer | 0.00 |
| software-architect | 0.00 |
### logistic

| career | top-1 recall |
|---|---|
| frontend | 0.81 |
| backend | 0.73 |
| data-science | 0.73 |
| devops | 0.94 |
| product-manager | 0.33 |
| ux-designer | 0.75 |
| fullstack | 0.92 |
| mobile | 0.75 |
| data-analyst | 0.71 |
| machine-learning | 0.87 |
| ai-engineer | 1.00 |
| cyber-security | 0.82 |
| qa-engineer | 0.75 |
| game-dev | 0.20 |
| technical-writer | 0.36 |
| software-architect | 0.43 |
### lightgbm

| career | top-1 recall |
|---|---|
| frontend | 0.85 |
| backend | 0.47 |
| data-science | 0.87 |
| devops | 1.00 |
| product-manager | 0.67 |
| ux-designer | 0.83 |
| fullstack | 0.92 |
| mobile | 0.62 |
| data-analyst | 0.94 |
| machine-learning | 0.93 |
| ai-engineer | 1.00 |
| cyber-security | 1.00 |
| qa-engineer | 0.69 |
| game-dev | 0.20 |
| technical-writer | 0.27 |
| software-architect | 0.64 |
### small_nn

| career | top-1 recall |
|---|---|
| frontend | 0.66 |
| backend | 0.60 |
| data-science | 0.60 |
| devops | 0.83 |
| product-manager | 0.33 |
| ux-designer | 0.42 |
| fullstack | 0.77 |
| mobile | 0.62 |
| data-analyst | 0.76 |
| machine-learning | 0.73 |
| ai-engineer | 1.00 |
| cyber-security | 0.64 |
| qa-engineer | 0.56 |
| game-dev | 0.20 |
| technical-writer | 0.45 |
| software-architect | 0.50 |

## Gate 1 verdict (reframed: calibration + stability, NOT beats-the-formula)

The gate is existential: it passes if any learned model clears BOTH thresholds
(ECE <= 0.1, stability >= 0.6).

| model | ECE | calibrated? | top-2 stability | stable? | verdict |
|---|---|---|---|---|---|
| logistic | 0.034 | yes | 0.638 | yes | QUALIFIES |
| lightgbm | 0.128 | NO | 0.557 | NO | — |
| small_nn | 0.062 | yes | 0.615 | yes | QUALIFIES |

- Preferred candidate (best-calibrated qualifier): **logistic**
  (ECE 0.034, stability 0.638)
- **Gate 1: PASSED — proceed to Phase 3**

The old criterion ("beat the formula on panel agreement") is reported above for
transparency but is not meaningful under key-anchored labeling — a model wins it by
learning the bonus table (see caveat a).

### Determinism precondition (passed — otherwise this report would not exist)

Every **trained** candidate above (`logistic`, `lightgbm`, `small_nn`) was fitted
twice on identical data and required to produce bit-identical probabilities before
any stability number was computed. (`formula` and `archetype_nn` are training-free,
so there is nothing to check.) The gated stability column reads all sub-model
disagreement as training-subset variation; for an estimator whose own refits
disagree, that reading is false and the number would be strictly noisier than its
competitors'. The run aborts rather than reporting a stability figure the Gate-1
0.6 stability threshold could then fire on as a measurement artifact.

### Reseeded stability of `small_nn` — reported, NOT gated

**0.667** — mean pairwise top-2 Jaccard across
3 refits that differ **only** in `random_state`. Compare against its
gated **0.615**, where the seed is fixed and the training subset
varies instead.

The two are computed over the same outer folds, the same inner resamples and the
same test rows, so they differ in **what varies and nothing else** — seed at fixed
subset here, subset at fixed seed there. That matching is what makes the
side-by-side reading legitimate: refitting these on the full training partition
would have been cheaper and would have confounded seed sensitivity with a larger
training set.

The reseeded number is deliberately kept out of the gate. Folding seed sensitivity
into it would penalise the network for a property logistic and lightgbm are never
measured on, and the comparison between models would stop being like-for-like.
Dropping it would hide a real property of the architecture: how much of a user's
recommendation depends on where training happened to start.

Additional notes:
- 7 real profiles ride along in the pool; far too few
  for a separate evaluation slice.
