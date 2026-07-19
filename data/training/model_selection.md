# Model Selection — Phase 3 / Gate 2

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Calibration (temperature) fitted on pooled
> out-of-fold predictions — prototype-grade; redo on gold labels before trusting
> displayed percentages.

Generated: 2026-07-19T16:03:27Z
Dataset: 232 rows, feature `features-v4`, seed 42,
outer 5-fold stratified CV (same folds as Phase 2).
Phase 2 reference (recomputed on THIS dataset, not hardcoded from a previous run):
production-formula top-2 agreement 0.582; full Phase-2 comparison
in baseline_evaluation.md.

## Comparison (pooled out-of-fold)

| model | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE raw | ECE scaled | T |
|---|---|---|---|---|---|---|---|---|
| gbt_tuned (3a) | 0.772 | 0.892 | 0.940 | 0.856 | 0.715 | 0.135 | 0.047 | 1.65 |
| logistic_tuned (3a) | 0.724 | 0.849 | 0.931 | 0.826 | 0.679 | 0.103 | 0.103 | 1.00 |
| small_nn soft-targets (3b) | 0.634 | 0.841 | 0.918 | 0.780 | 0.572 | 0.130 | 0.101 | 0.90 |
| two_tower archetype-seeded (3c) | 0.634 | 0.746 | 0.828 | 0.747 | 0.566 | 0.047 | 0.077 | 1.30 |

Chosen hyperparameters per outer fold:
- gbt (n_estimators, lr, num_leaves, min_child_samples): [(200, 0.07, 7, 3), (200, 0.03, 7, 3), (200, 0.03, 15, 3), (200, 0.07, 7, 10), (200, 0.07, 15, 3)]
- logistic C: [4.0, 4.0, 4.0, 0.05, 0.25]

## Per-class top-1 recall

### gbt_tuned

| career | top-1 recall |
|---|---|
| frontend | 0.83 |
| backend | 0.53 |
| data-science | 0.87 |
| devops | 1.00 |
| product-manager | 0.67 |
| ux-designer | 0.67 |
| fullstack | 0.92 |
| mobile | 0.50 |
| data-analyst | 0.94 |
| machine-learning | 1.00 |
| ai-engineer | 1.00 |
| cyber-security | 0.91 |
| qa-engineer | 0.69 |
| game-dev | 0.00 |
| technical-writer | 0.27 |
| software-architect | 0.64 |
### logistic_tuned

| career | top-1 recall |
|---|---|
| frontend | 0.79 |
| backend | 0.73 |
| data-science | 0.67 |
| devops | 0.94 |
| product-manager | 0.33 |
| ux-designer | 0.67 |
| fullstack | 0.85 |
| mobile | 0.75 |
| data-analyst | 0.76 |
| machine-learning | 0.87 |
| ai-engineer | 1.00 |
| cyber-security | 0.73 |
| qa-engineer | 0.69 |
| game-dev | 0.20 |
| technical-writer | 0.45 |
| software-architect | 0.43 |
### small_nn

| career | top-1 recall |
|---|---|
| frontend | 0.79 |
| backend | 0.73 |
| data-science | 0.87 |
| devops | 0.83 |
| product-manager | 0.50 |
| ux-designer | 0.58 |
| fullstack | 0.69 |
| mobile | 0.25 |
| data-analyst | 0.59 |
| machine-learning | 0.80 |
| ai-engineer | 0.67 |
| cyber-security | 0.45 |
| qa-engineer | 0.44 |
| game-dev | 0.20 |
| technical-writer | 0.55 |
| software-architect | 0.21 |
### two_tower

| career | top-1 recall |
|---|---|
| frontend | 0.77 |
| backend | 0.53 |
| data-science | 0.67 |
| devops | 0.94 |
| product-manager | 0.00 |
| ux-designer | 0.50 |
| fullstack | 0.85 |
| mobile | 0.50 |
| data-analyst | 0.82 |
| machine-learning | 0.53 |
| ai-engineer | 1.00 |
| cyber-security | 0.82 |
| qa-engineer | 0.56 |
| game-dev | 0.20 |
| technical-writer | 0.00 |
| software-architect | 0.36 |

## Gate 2 verdict

**Winner: `gbt_tuned`** — top-2 0.892, ECE after temperature
scaling 0.047 (T=1.65).
Selection rule: highest top-2; ties within 0.01 broken by scaled ECE.

## Deployment selection

**Deployable winner: `logistic_tuned`** — gate2 winner 'gbt_tuned' has no serving path (matcher_model.py is linear-only with exact attribution — the Phase-4 explainability requirement); logistic is the Gate-1-qualified deployable selection.
export_model.py refuses to export unless this names the architecture it produces
(and refuses outright when it is NONE), so the served artifact and this report
cannot silently disagree — and a Gate-1-rejected model can never ship.

Notes:
- The soft-target NN consumes the panel vote distribution (top1=1.0, top2=0.4);
  the other models train on hard consensus labels with class weights.
- two_tower remains the only architecture that admits a new career without
  retraining (one archetype vector); keep it as future work even if it loses here.
