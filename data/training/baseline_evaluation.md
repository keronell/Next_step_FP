# Baseline Evaluation — Phase 2 / Gate 1

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** A high number means the scorer predicts the panel's
> labels; it does not certify real-world recommendation quality.

Generated: 2026-07-04T08:26:00Z
Dataset: 205 rows ({'synthetic': 198, 'real': 7}), feature version `features-v1`,
Chroma snapshot 1575 docs.
Protocol: stratified 5-fold CV (seed 42); metrics on pooled out-of-fold
predictions. Trained scorers use class weights (labels are imbalanced: PM=14, FE=17).

## Comparison

| scorer | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE* |
|---|---|---|---|---|---|---|
| formula (production) | 0.439 | 0.668 | 0.829 | 0.646 | 0.389 | 0.119 |
| archetype_nn (zero-train) | 0.327 | 0.595 | 0.824 | 0.575 | 0.335 | 0.135 |
| logistic (balanced) | 0.756 | 0.932 | 0.971 | 0.864 | 0.723 | 0.103 |
| lightgbm (balanced) | 0.761 | 0.927 | 0.971 | 0.866 | 0.696 | 0.168 |

*ECE for `formula` and `archetype_nn` is computed on softmax-normalized scores
(pseudo-probabilities) — directional only. Trained models emit real probabilities.

## Per-class top-1 recall

### formula

| career | top-1 recall |
|---|---|
| frontend | 0.12 |
| backend | 0.00 |
| data-science | 0.44 |
| devops | 0.97 |
| product-manager | 0.00 |
| ux-designer | 0.81 |
### archetype_nn

| career | top-1 recall |
|---|---|
| frontend | 0.47 |
| backend | 0.14 |
| data-science | 0.38 |
| devops | 0.55 |
| product-manager | 0.21 |
| ux-designer | 0.25 |
### logistic

| career | top-1 recall |
|---|---|
| frontend | 0.65 |
| backend | 0.72 |
| data-science | 0.86 |
| devops | 0.74 |
| product-manager | 0.57 |
| ux-designer | 0.81 |
### lightgbm

| career | top-1 recall |
|---|---|
| frontend | 0.59 |
| backend | 0.74 |
| data-science | 0.92 |
| devops | 0.68 |
| product-manager | 0.36 |
| ux-designer | 0.89 |

## Gate 1 verdict

- Formula top-2 agreement: **0.668**
- Best learned model: **logistic** at top-2 **0.932**
  (margin +0.263; threshold for "meaningful" set at +0.05)
- **Gate 1: PASSED — proceed to Phase 3**

Caveats:
- Circularity: the formula's inputs (fit/sem/skill) are also model features, and
  formula-vs-panel top-1 agreement was 43.4% at labeling time — partial circularity
  in both directions; see synthetic_agreement_report.md.
- 7 real profiles ride along in the pool; far too few
  for a separate evaluation slice.
