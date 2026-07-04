# Model Selection — Phase 3 / Gate 2

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Calibration (temperature) fitted on pooled
> out-of-fold predictions — prototype-grade; redo on gold labels before trusting
> displayed percentages.

Generated: 2026-07-04T08:31:39Z
Dataset: 205 rows, feature `features-v1`, seed 42,
outer 5-fold stratified CV (same folds as Phase 2).
Phase 2 references: formula top-2 0.668; logistic (default) top-2 0.932; lightgbm
(default) top-2 0.927.

## Comparison (pooled out-of-fold)

| model | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE raw | ECE scaled | T |
|---|---|---|---|---|---|---|---|---|
| gbt_tuned (3a) | 0.756 | 0.902 | 0.971 | 0.859 | 0.707 | 0.186 | 0.051 | 2.60 |
| logistic_tuned (3a) | 0.776 | 0.937 | 0.976 | 0.875 | 0.734 | 0.065 | 0.086 | 0.85 |
| small_nn soft-targets (3b) | 0.722 | 0.922 | 0.976 | 0.846 | 0.706 | 0.199 | 0.075 | 0.45 |
| two_tower archetype-seeded (3c) | 0.629 | 0.834 | 0.922 | 0.780 | 0.598 | 0.062 | 0.060 | 1.15 |

Chosen hyperparameters per outer fold:
- gbt (n_estimators, lr, num_leaves, min_child_samples): [(400, 0.07, 15, 10), (400, 0.03, 15, 3), (200, 0.07, 15, 10), (400, 0.03, 7, 10), (200, 0.07, 15, 3)]
- logistic C: [0.25, 0.25, 0.25, 0.25, 0.05]

## Per-class top-1 recall

### gbt_tuned

| career | top-1 recall |
|---|---|
| frontend | 0.65 |
| backend | 0.72 |
| data-science | 0.90 |
| devops | 0.68 |
| product-manager | 0.43 |
| ux-designer | 0.86 |
### logistic_tuned

| career | top-1 recall |
|---|---|
| frontend | 0.59 |
| backend | 0.72 |
| data-science | 0.90 |
| devops | 0.82 |
| product-manager | 0.57 |
| ux-designer | 0.81 |
### small_nn

| career | top-1 recall |
|---|---|
| frontend | 0.53 |
| backend | 0.68 |
| data-science | 0.74 |
| devops | 0.74 |
| product-manager | 0.71 |
| ux-designer | 0.83 |
### two_tower

| career | top-1 recall |
|---|---|
| frontend | 0.35 |
| backend | 0.56 |
| data-science | 0.58 |
| devops | 0.82 |
| product-manager | 0.50 |
| ux-designer | 0.78 |

## Gate 2 verdict

**Winner: `logistic_tuned`** — top-2 0.937, ECE after temperature
scaling 0.086 (T=0.85).
Selection rule: highest top-2; ties within 0.01 broken by scaled ECE.

Notes:
- The soft-target NN consumes the panel vote distribution (top1=1.0, top2=0.4);
  the other models train on hard consensus labels with class weights.
- two_tower remains the only architecture that admits a new career without
  retraining (one archetype vector); keep it as future work even if it loses here.
