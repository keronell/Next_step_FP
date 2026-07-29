# Model Selection — Phase 3 / Gate 2

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Calibration is now **cross-fitted**: the temperature
> is fitted per outer fold on inner out-of-fold predictions drawn only from that
> fold's training partition, never from the rows it goes on to score (ADR 0004).
> Circularity is a separate, untouched defect — better labels would not have fixed
> this one, and this fix does not make the labels less circular.

## !! DELIBERATE BREAK FROM RECORDED HISTORY !!

**Every Gate-2 calibration number in this report is non-comparable to any version
generated before 2026-07-28 (DEV-91)**, including the `gbt_tuned` ECE
0.047 that won it Gate 2 under the old
protocol. The break was a deliberate one-time re-baseline of all four models in a
single run, not drift.

This section stays in every future report, because the non-comparability is
permanent: it describes the boundary, not this particular run. The table further
down recomputes both sides each time, so it keeps telling the truth as the code
moves on.

What moved and why:

- **One column only, for `gbt_tuned` and `logistic_tuned`.** Temperature scaling is
  monotone within a row, so it cannot reorder anything: their top-1/2/3, MRR,
  balanced top-1 and per-class recall are unchanged, and `ECE raw` is unchanged.
  Their *deployment* temperatures also reproduce the recorded 1.65 and 1.00
  exactly, because that number is still fitted on the full pool. What is new for
  them is the cross-fitted ECE and the five per-fold temperatures behind it.
- **`small_nn` moved for TWO independent reasons** and the movement must not be
  attributed to cross-fitting alone. (1) This change. (2) DEV-90 replaced the
  inline network with the shared `nn_model.NNClassifier`, which re-seeds torch per
  fit where the old inline code inherited accumulated process-global RNG state. Its
  recorded row was already stale before this run.

  **The two causes separate exactly, from the table below.** Its recorded
  `ECE scaled` of 0.101 was the old protocol on the old inline network. The
  `ECE pooled-T (legacy)` column is the old protocol on DEV-90's shared network, so
  `0.101 -> legacy` is DEV-90's re-seeding alone and `legacy -> cross-fitted` is
  this ticket alone. The split is exact here because `NNClassifier` restores global
  RNG state around every fit, which makes its raw OOF independent of how many fits
  preceded it. It is **not** exact for `two_tower`, for the reason below.
- **`two_tower` moved for a second reason too.** Unlike `NNClassifier`, it seeds
  from process-global torch RNG rather than per fit, so its predictions depend on
  how many fits preceded them — and cross-fitting inserts three per outer fold.
  Its numbers are reproducible from a clean run but order-dependent. Left as-is
  rather than fixed here: making it deterministic would be a second uncontrolled
  change to a model's identity inside the very run meant to re-baseline it.
- **Say plainly what that means: for `small_nn` and `two_tower` the RANKING metrics
  moved, not only the calibration ones** — including top-2, which is the Gate-2
  *primary*, not a tiebreak input. `small_nn` top-2 0.841 ->
  0.845, `two_tower` 0.746 ->
  0.763. This run does not isolate the protocol for
  those two, and the honest reading is that their rows are a fresh baseline rather
  than a comparison. The contender set happened to be unaffected — see the verdict
  — but a larger shift could have changed it.

The dataset is unmoved: digest `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`, the
same build both gate files were computed on.

**Gate 1 is unaffected, and that was verified rather than assumed.**
`evaluate_matchers.py` was re-run on unchanged code and reproduced the digest and
every Gate-1 metric to the last digit. Those metrics, read back from the
`gate1_verdict.json` this run consumed rather than transcribed:

| model | Gate-1 ECE (raw, never tempered) | top-2 stability |
|---|---|---|
| logistic | 0.034099440082920096 | 0.637516702641587 |
| lightgbm | 0.128155228434309 | 0.5566450817144618 |
| small_nn | 0.06183095636038942 | 0.6153150375167026 |

Gate 1 is also unaffected structurally, which is the stronger statement: it gates
on RAW ECE, has never applied a temperature, and `evaluate_matchers.py` does not
import this module in either direction.

Generated: 2026-07-29T16:47:04Z
Dataset: 232 rows, feature `features-v4`, seed 42,
outer 5-fold stratified CV (same folds as Phase 2).
Phase 2 reference (recomputed on THIS dataset, not hardcoded from a previous run):
production-formula top-2 agreement 0.582; full Phase-2 comparison
in baseline_evaluation.md.

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

## Comparison (pooled out-of-fold)

| model | top-1 | top-2 | top-3 | MRR | balanced top-1 | ECE raw | ECE cross-fitted | ECE pooled-T (legacy) |
|---|---|---|---|---|---|---|---|---|
| gbt_tuned (3a) | 0.772 | 0.892 | 0.940 | 0.856 | 0.715 | 0.135 | 0.040 | 0.047 |
| logistic_tuned (3a) | 0.724 | 0.849 | 0.931 | 0.826 | 0.679 | 0.103 | 0.061 | 0.103 |
| small_nn soft-targets (3b) | 0.603 | 0.845 | 0.918 | 0.765 | 0.528 | 0.095 | 0.102 | 0.078 |
| two_tower archetype-seeded (3c) | 0.638 | 0.763 | 0.828 | 0.753 | 0.562 | 0.062 | 0.081 | 0.086 |
| residual_matcher hard-labels (3d) | 0.724 | 0.849 | 0.931 | 0.826 | 0.679 | 0.103 | 0.061 | 0.103 |

**`ECE cross-fitted` is the reported and gating number.** `ECE pooled-T (legacy)`
is what the old protocol printed — one temperature fitted on the whole OOF pool and
then scored on that same pool. It is shown to size the defect and to separate
`small_nn`'s two causes. It is not a metric.

## Break from recorded history, side by side

The last run under the old protocol (2026-07-19) against this one. `legacy`
columns are computed here, so a matching pair proves the environment and the raw
predictions are unmoved and isolates the change to the protocol alone.

| model | recorded ECE raw | now | recorded ECE scaled | now (legacy) | reproduces? |
|---|---|---|---|---|---|
| gbt_tuned | 0.135 | 0.135 | 0.047 | 0.047 | **exact** |
| logistic_tuned | 0.103 | 0.103 | 0.103 | 0.103 | **exact** |
| small_nn | 0.130 | 0.095 | 0.101 | 0.078 | no — see causes above |
| two_tower | 0.047 | 0.062 | 0.077 | 0.086 | no — see causes above |

`residual_matcher` is absent from that table by construction: it is new in DEV-93,
was never scored under the old protocol, and a model with no recorded row can
neither reproduce nor fail to reproduce one.

## What this re-baseline showed

**1. 2 of 4 models with recorded history reproduce the old protocol exactly**
(`gbt_tuned`, `logistic_tuned`). Their `ECE raw` and their
`legacy` ECE match the 2026-07-19 record to three decimals — same environment, same
folds, same raw out-of-fold predictions — which isolates the whole of their movement
to the protocol change. The models absent from that list are the two with a
documented second cause, above.

**2. `small_nn`'s two causes are each large and nearly cancel.** Recorded 0.101 ->
legacy 0.078 is DEV-90's per-fit re-seeding
alone (a move of
0.023);
legacy -> cross-fitted 0.102 is this ticket
alone (a move of
0.025).
They point in opposite directions, so the net move from the recorded number is only
0.001.
**Attributing that net to cross-fitting alone would have been wrong in both
magnitude and sign.**

**3. The old number moves in no predictable direction, and that is not a flaw in
the fix.** The guarantee is narrower than it first looks, and worth stating
precisely because two drafts of this report got it wrong.

Within the family of **constant** temperatures, a temperature fitted on a pool is
the argmin of NLL on that pool: no other constant can score lower there. *That* is
the leak — the old number was a fitted minimum, not a measurement.

But cross-fitting changes two things at once. It removes the leak, **and** it
widens the family from one global constant to five per-fold constants, which can
absorb fold-specific miscalibration a single constant cannot. The second effect
can outweigh the first, and here it does: cross-fitted ECE is *lower* for
4 of 5
(`gbt_tuned`, `logistic_tuned`, `two_tower`, `residual_matcher`), and cross-fitted NLL is
lower for 2 of 5. So the honest claim is only this: **the old number was never a
held-out estimate.** Not that it was necessarily flattering. ADR 0004's word
"optimistic" is right about the mechanism and overstated as a prediction about
either metric, and is annotated accordingly.

| model | NLL cross-fitted | NLL pooled-T (legacy) | which is lower |
|---|---|---|---|
| gbt_tuned | 0.7415 | 0.7382 | legacy |
| logistic_tuned | 0.9096 | 0.9685 | cross-fitted |
| small_nn | 1.1304 | 1.1256 | legacy |
| two_tower | 1.2979 | 1.2754 | legacy |
| residual_matcher | 0.9096 | 0.9685 | cross-fitted |

Neither column is a gate input; both are shown because the direction is the thing
readers will assume they already know.

## Calibration temperature, per outer fold

| model | fold 1 | 2 | 3 | 4 | 5 | spread | sd | Phase-3 pooled T |
|---|---|---|---|---|---|---|---|---|
| gbt_tuned | 1.95 | 1.70 | 1.75 | 1.90 | 1.85 | 0.25 | 0.09 | 1.65 |
| logistic_tuned | 1.40 | 1.40 | 1.30 | 0.50 | 0.85 | 0.90 | 0.36 | 1.00 |
| small_nn | 0.90 | 0.90 | 1.05 | 1.10 | 1.15 | 0.25 | 0.10 | 0.90 |
| two_tower | 1.30 | 1.15 | 1.45 | 1.60 | 1.45 | 0.45 | 0.15 | 1.45 |
| residual_matcher | 1.40 | 1.40 | 1.30 | 0.50 | 0.85 | 0.90 | 0.36 | 1.00 |

**The spread is itself a finding, and the widest of it is on the model that ships.**
Each fold's temperature is an independent estimate of the same quantity, so a wide
spread means a single temperature is not a well-estimated quantity.
`logistic_tuned`, the deployment architecture, has a spread of
0.90 across
1.40, 1.40, 1.30, 0.50, 0.85: folds disagree about
whether its probabilities need softening or sharpening at all, and **no fold chose the pooled 1.00 Phase-3 reference**.
Read that as a warning about displayed `matchPercent` precision, not about the
ranking — temperature cannot reorder anything.

The `Phase-3 pooled T` column is fitted separately on each model's full pooled OOF.
It is a reference for the evaluated configuration, not a transferable artifact
field. Export selects a fixed C and independently fits the one shipped constant on
OOF predictions from that exact configuration.

Chosen hyperparameters per outer fold:
- gbt (n_estimators, lr, num_leaves, min_child_samples): [(200, 0.07, 7, 3), (200, 0.03, 7, 3), (200, 0.03, 15, 3), (200, 0.07, 7, 10), (200, 0.07, 15, 3)]
- logistic C: [4.0, 4.0, 4.0, 0.05, 0.25]
- residual (alpha, inherited logistic C): [(0.0, 4.0), (0.0, 4.0), (0.0, 4.0), (0.0, 0.05), (0.0, 0.25)]

## Residual Matcher: the pre-registered alpha=0 rule

`alpha` is a hyperparameter selected by inner CV from [0.0, 0.25, 0.5, 1.0], and at
`alpha = 0` the model is *exactly* logistic regression. ADR 0003 pre-registered,
before any alpha was selected on this data, that **alpha=0 in >= 3
of 5 outer folds is reported as "no non-linear signal found"** and disqualifies the
Residual Matcher from being the shipped neural model — shipping it would be
shipping logistic regression in a costume while the project requires a neural
network (ADR 0001).

Per-fold alpha: [0.0, 0.0, 0.0, 0.0, 0.0] — 5 of 5 at zero.
**Verdict: NO NON-LINEAR SIGNAL FOUND — disqualified from being the shipped neural model.**
The inherited logistic C per fold: [4.0, 4.0, 4.0, 0.05, 0.25]. Reporting only —
nothing here selects, and a disqualified Residual Matcher is still reported in full.

**Its row in the comparison table above is identical to `logistic_tuned`'s in every column, and that is a consequence rather than a coincidence.**
At `alpha = 0` the Residual Matcher is exactly logistic regression at its inherited `C`, and that `C` comes from the same `select_by_inner_cv` call `logistic_tuned` uses — verified here, not assumed: the per-fold `C` lists match. With every fold at `alpha = 0` the two are therefore the same estimator, fold for fold, and no arithmetic could separate them. Read the two rows as one measurement printed twice.

What this does NOT establish: that a non-linear residual could never help on these
features. It establishes that inner CV, given the choice on this dataset under this
protocol, declined it in every fold — which is evidence about this feature set and
this sample size, not a theorem. The 5-seed sweep in `nn_rework.md` is the wider
test, and it reaches the same verdict.

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
| frontend | 0.77 |
| backend | 0.60 |
| data-science | 0.80 |
| devops | 0.78 |
| product-manager | 0.33 |
| ux-designer | 0.50 |
| fullstack | 0.62 |
| mobile | 0.12 |
| data-analyst | 0.65 |
| machine-learning | 0.73 |
| ai-engineer | 0.78 |
| cyber-security | 0.36 |
| qa-engineer | 0.44 |
| game-dev | 0.00 |
| technical-writer | 0.55 |
| software-architect | 0.43 |
### two_tower

| career | top-1 recall |
|---|---|
| frontend | 0.81 |
| backend | 0.73 |
| data-science | 0.73 |
| devops | 0.83 |
| product-manager | 0.00 |
| ux-designer | 0.50 |
| fullstack | 0.77 |
| mobile | 0.62 |
| data-analyst | 0.71 |
| machine-learning | 0.47 |
| ai-engineer | 1.00 |
| cyber-security | 0.82 |
| qa-engineer | 0.50 |
| game-dev | 0.00 |
| technical-writer | 0.00 |
| software-architect | 0.50 |
### residual_matcher

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

## Gate 2 verdict

**Winner: `gbt_tuned`** — top-2 0.892, cross-fitted ECE
0.040 (per-fold T
1.95, 1.70, 1.75, 1.90, 1.85).
Selection rule: highest top-2; ties within 0.01 broken by **cross-fitted** ECE.

**The tiebreak did NOT fire this run.**
`gbt_tuned` wins on top-2 alone (0.892 against a runner-up 0.849, outside the 0.01 band), so the ECE column decided nothing.
Stated rather than left for the reader to infer, so the calibration figure printed
beside the verdict is not mistaken for the thing that chose it. What this ticket
changed is which quantity *would* decide a close call: the legacy
pooled number's bias is model-dependent — a worse-calibrated model gains more from
fitting T on its own evaluation data — so the tiebreak was the statistic most
distorted by the defect, and is now the honest one.

## Deployment selection

**Deployable winner: `logistic_tuned`** — gate2 winner 'gbt_tuned' has no serving path (matcher_model.py is linear-only with exact attribution — the Phase-4 explainability requirement); logistic is the Gate-1-qualified deployable selection.
export_model.py refuses to export unless this names the architecture it produces
(and refuses outright when it is NONE), so the served artifact and this report
cannot silently disagree — and a Gate-1-rejected model can never ship.

The deployment temperature recorded for `logistic_tuned` is
1.00,
for Phase 3's per-fold-selected configuration. export_model.py requires this
calibration record as provenance but does not transfer its temperature when
serializing a different configuration: it selects one fixed C and refits on OOF
predictions from that exact C. **DEV-88 made the serving path divide logits by the
artifact's refitted field**, so any non-1.0 value changes served `matchPercent`.

Notes:
- The soft-target NN consumes the panel vote distribution (top1=1.0, top2=0.4);
  the other models train on hard consensus labels with class weights.
- two_tower remains the only architecture that admits a new career without
  retraining (one archetype vector); keep it as future work even if it loses here.
