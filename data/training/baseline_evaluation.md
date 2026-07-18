# Baseline Evaluation — Phase 2 / Gate 1 (reframed)

> **CAVEATS THAT TRAVEL WITH EVERY RESULT BELOW**
> (a) Silver labels are **bank-consistent, not independently validated**: the
> panel's stage-2 vote follows the answer key derived from careers.json bonuses
> ~94% of the time it speaks. In this dataset the labels agree with the
> questionnaire-only heuristic fit (the answer-key winner) **52.2%**
> of the time, and with the full production formula (fit+sem+skill) top-1
> **46.1%** of the time. Panel-agreement numbers measure
> fidelity to the hand-authored bonus table, nothing more — Gate 1 no longer uses them.
> (b) **game-dev has floor-level representation** (5 labels,
> the 5-per-class minimum) — treat every game-dev metric and prediction as
> low-confidence.
> (c) **frontend is over-represented** (47/232 rows,
> 20%) as spillover from compensating game-dev's ~10%
> panel-labelability; see the class-balance table.

Generated: 2026-07-18T17:14:09Z
Dataset: 232 rows ({'synthetic': 225, 'real': 7}), feature version `features-v4`,
labels `panel-v2.1.0`, Chroma snapshot 1853 docs.
Protocol: stratified 5-fold CV (seed 42); metrics on pooled out-of-fold
predictions. Both trained scorers use class_weight="balanced".

## Comparison (panel agreement is DESCRIPTIVE only — see caveat a)

| scorer | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE* | top-2 stability |
|---|---|---|---|---|---|---|---|
| formula (production) | 0.461 | 0.582 | 0.659 | 0.611 | 0.493 | 0.162 | 1.000** |
| archetype_nn (zero-train) | 0.099 | 0.250 | 0.353 | 0.284 | 0.102 | 0.133 | 1.000** |
| logistic (balanced) | 0.741 | 0.871 | 0.927 | 0.838 | 0.694 | 0.034 | 0.638 |
| lightgbm (balanced) | 0.789 | 0.871 | 0.914 | 0.858 | 0.744 | 0.128 | 0.557 |

*ECE for `formula` and `archetype_nn` is computed on softmax-normalized scores
(pseudo-probabilities) — directional only. Trained models emit real probabilities.
**Static scorers involve no training, so resampling stability is 1.0 by construction.

## Class balance: label share vs predicted share (over-prediction check)

| career | label share | formula pred | logistic pred | lightgbm pred |
|---|---|---|---|---|
| frontend | 20.3% | 6.0% | 19.8% | 22.0% |
| backend | 6.5% | 0.9% | 6.5% | 4.7% |
| data-science | 6.5% | 4.3% | 7.8% | 6.9% |
| devops | 7.8% | 6.9% | 8.2% | 8.2% |
| product-manager | 2.6% | 0.9% | 2.2% | 3.0% |
| ux-designer | 5.2% | 3.9% | 5.2% | 5.2% |
| fullstack | 5.6% | 26.3% | 5.6% | 6.5% |
| mobile | 3.4% | 5.2% | 3.4% | 3.9% |
| data-analyst | 7.3% | 14.2% | 6.9% | 6.9% |
| machine-learning | 6.5% | 6.0% | 6.0% | 6.0% |
| ai-engineer | 3.9% | 2.6% | 4.3% | 3.9% |
| cyber-security | 4.7% | 3.4% | 5.2% | 5.6% |
| qa-engineer | 6.9% | 1.7% | 6.5% | 6.9% |
| game-dev | 2.2% | 9.9% | 3.0% | 2.2% |
| technical-writer | 4.7% | 3.0% | 4.7% | 3.0% |
| software-architect | 6.0% | 4.7% | 4.7% | 5.2% |

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

## Gate 1 verdict (reframed: calibration + stability, NOT beats-the-formula)

- Best-calibrated learned model: **logistic**
- Pooled OOF ECE: **0.034** (threshold <= 0.1)
- Top-2 stability (mean pairwise fold-model Jaccard): **0.638** (threshold >= 0.6)
- **Gate 1: PASSED — proceed to Phase 3**

The old criterion ("beat the formula on panel agreement") is reported above for
transparency but is not meaningful under key-anchored labeling — a model wins it by
learning the bonus table (see caveat a).

Additional notes:
- 7 real profiles ride along in the pool; far too few
  for a separate evaluation slice.
