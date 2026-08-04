# Neural Matcher Rework -- the learning curve

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Circularity is untouched here and is a separate defect
> from Leakage: the labels reproduce the `careers.json` answer key, so every number
> below measures fidelity to a hand-authored bonus table. Measuring that fidelity at
> five dataset sizes does not make it less circular, and this report does not claim
> it does.

DEV-96, plan `docs/dev-23-nn-rework-plan.md` Step 2.6. Vocabulary is `CONTEXT.md`'s.

Generated: 2026-07-31T09:33:33Z
Dataset: 232 rows, feature `features-v4`, digest `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`.
Experiment seeds: [42, 43, 44, 45, 46].

## Summary

1. **The gap is flat / inconclusive against both comparators** under the pre-registered rule, which asks only whether
   the CI on Delta-gap excludes zero in the narrowing direction.
2. **The neural matcher itself improves steeply with n -- from 0.635 top-2 at n=80 to 0.820 at n=232, +0.185 -- and so do both comparators (`logistic_tuned` +0.125, `gbt_tuned` +0.206).** More data plainly helps
   the model; what it does not do, measurably, is change how it stands RELATIVE to the
   alternatives. Those are different claims and only the second is what the verdict
   above refers to.
3. **The class-balance confound is not controlled by the main curve.** Class-floored
   subsampling puts the max:min skew at 1.00 at n=48 rising to 9.40 at n=232, so balance
   and n move together at every point below.
4. **The curve measures a FIVE-MEMBER ENSEMBLE**, because that is what DEV-95
   selected. Every neural fit here is 5 networks.
5. **These numbers are not comparable to any gate number.** Different fold count,
   different inner protocol, subsampled data.

## !! NOT COMPARABLE TO THE 5-FOLD GATE NUMBERS !!

Everything here comes from a **dedicated 3-fold protocol on subsampled
data**, with comparator selection under 2 inner folds. Gate 1,
Gate 2, Round 1 and Round 2 all use 5 outer folds and
3 inner ones on all 232 rows. A top-2 number below is
a different measurement from a top-2 number there, not a later reading of the same
one, and the two must not be presented as a series. The Round-2 effect sizes remain
the deliverable's statement of where the neural matcher stands; this report is only
about how that standing MOVES with n.

## What this measures, and what it is for

**The curve is evidence, not a gate.** Under ADR 0004 the neural matcher ships either
way. What this sizes is whether more labels would close the gap to the alternatives --
a direct input to whether funding a bigger dataset is worth it, and the most
actionable output of DEV-23. It is not a re-selection and it cannot become one.

**The frozen model is FIVE networks, not one.** Plan Step 2.6 freezes architecture and
hyperparameters at the selected configuration, and DEV-95 selected
`D5_ensemble_dropout_0.5_wd_1e-2` -- a `nn_model.SeedEnsemble` of 5
`NNClassifier` members seeded `random_state + i`, at dropout
0.5 and weight decay 0.01, every
other hyperparameter at the defaults. **Every fit on the neural leg below is
5 fits.** A reader who assumes one network will misread the compute,
and will misread what "the model" means when DEV-97 exports it.

The specification is read from `selected_specification` in `round2_results.json` and
checked against the registry entry field by field, so the curve cannot quietly measure
a later edit of the configuration DEV-95 chose.

**Epoch count is NOT frozen.** Freezing the configuration is not freezing the epoch
budget: early stopping still chooses the epoch per fit, under one validation rule at
every point. A frozen budget tuned at n=232 would over-train the
small-n points and manufacture the very narrowing this curve tests for.

**The validation rule, one rule everywhere:** `n_val = max(n_classes,
ceil(0.15 * n_train))`. It is expressed through an additive
absolute-size argument rather than a per-point fraction, because `val_fraction` is a
float handed to `train_test_split` and `n_val / n_train` is not guaranteed to round
back to the integer it came from. Every fit asserts that the split held out exactly
`n_val` rows. The argument's default is inert, so the control Variant and `small_nn`'s
recorded Gate-1 numbers still describe the same estimator.

**The comparators are NESTED at every point, not frozen at one configuration.** This
is a design decision plan Step 2.6 left open, and the comparison means something
different depending on the answer, so it is stated rather than assumed.
`gbt_tuned` re-selects from its 16-point grid and `logistic_tuned`
from its 4 at every (point, fold, seed) -- 33x the GBT
cost of freezing, since selecting costs 16 grid points times
2 inner folds plus the refit, against one fit. The alternative was rejected on
correctness rather than budget: freezing means either an arbitrary configuration,
which is no longer the `gbt_tuned` the rest of this deliverable reports a gap against,
or one selected on all 232 rows -- which would have seen data outside every
subsample below 232, and that is Leakage in the sense `CONTEXT.md` reserves
the word for, at four of the five points.

**The comparator legs are computed FRESH, not reused from Round 1 or Round 2.** Those
rounds could legitimately reuse each other's, because within a seed the fold partition
is a function of the seed alone *under the same protocol*. This is a different
protocol, so a reused leg would be a model scored on a different partition -- and
nothing would have failed.

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

## The class-balance confound

Class-floored stratified subsampling gives every class at least 3
rows, and on this data that puts the skew at 1.00 at n=48 rising to 9.40 at n=232 across the main curve --
so the SMALL-n points are MORE balanced
than the large ones. Balance and n therefore move together, and plan Step 2.6 expects
them to push in opposite directions: small n harder for data-size reasons, easier for
balance reasons. **An observed narrowing could be a balance effect.** The skew is printed beside every gap for exactly that reason, and
the control curve below is the attempt -- a limited one -- to separate them.

## The main curve

`gap` is the comparator's top-2 lead over the neural matcher; positive means the
comparator is ahead. Each gap is a paired bootstrap over that point's own profiles,
with the profile as the sampling unit and a profile's 5
seeds averaged before differencing -- the same machinery, and the same kind of
interval, as the Round-2 effect sizes.

| point | skew | max:min | n_val | top-2 curve_nn | top-2 logistic_tuned | top-2 gbt_tuned | gap vs logistic_tuned | gap vs gbt_tuned |
|---|---|---|---|---|---|---|---|---|
| n=48 | 1.00 | 3:3 | 16 | 0.600 +/- 0.064 | 0.725 +/- 0.033 | 0.617 +/- 0.034 | +0.1250 [+0.0458, +0.2083] | +0.0167 [-0.0792, +0.1125] |
| n=80 | 3.67 | 11:3 | 16 | 0.635 +/- 0.022 | 0.725 +/- 0.027 | 0.660 +/- 0.022 | +0.0900 [+0.0375, +0.1450] | +0.0250 [-0.0500, +0.1000] |
| n=116 | 4.75 | 19:4 | 16 | 0.748 +/- 0.021 | 0.783 +/- 0.014 | 0.736 +/- 0.060 | +0.0345 [-0.0086, +0.0810] | -0.0121 [-0.0707, +0.0449] |
| n=174 | 8.25 | 33:4 | 18 | 0.810 +/- 0.016 | 0.830 +/- 0.008 | 0.840 +/- 0.016 | +0.0195 [-0.0092, +0.0494] | +0.0299 [-0.0092, +0.0690] |
| n=232 | 9.40 | 47:5 | 24 | 0.820 +/- 0.009 | 0.850 +/- 0.016 | 0.866 +/- 0.010 | +0.0302 [+0.0026, +0.0595] | +0.0466 [+0.0155, +0.0793] |

**n=48 is annotated "protocol floor -- 1 training example per class after the validation rule, not a data-size measurement".** It is reported so nobody can claim the hardest point was quietly dropped, and it is EXCLUDED from the pre-registered test below.

**Whether there is a gap at all, which is a different question from whether it
moves.** The pre-registered reading below is about the MOVEMENT; a reader who takes
"flat / inconclusive" as "no gap" would have it backwards.

- `logistic_tuned`: the gap CI excludes zero at 3 of 5 points (n=48 -- the protocol floor; n=80; n=232). At n=232 it is +0.0302 [+0.0026, +0.0595].
- `gbt_tuned`: the gap CI excludes zero at 1 of 5 points (n=232). At n=232 it is +0.0466 [+0.0155, +0.0793].

## The pre-registered reading

The quantity is **Delta-gap = gap(n=232) - gap(n=80)**, computed over the
80 profiles common to both points. That set exists
only because the subsamples are NESTED -- n=80's rows are a subset of n=232's --
which is a requirement of this design rather than a convenience, and is pinned by
`data/scripts/tests/test_learning_curve.py`.

**"Narrowing" means the CI on Delta-gap excludes zero in the narrowing direction.**
Anything else is reported as flat / inconclusive. **No trend is claimed from a
point-estimate slope**, which is the rule that replaced rev 2's non-overlapping-CIs
proxy -- a low-power test of a quantity nobody wanted.

Note that the `gap(n=232)` printed below is computed over those
80 common profiles and will therefore NOT equal the
`n=232` row of the table above, which is over all 232. Both are
correct; only the one below is comparable to `gap(n=80)`, and comparing the two
gaps on one population is the whole point of restricting to the common set.

- **`logistic_tuned`: FLAT / INCONCLUSIVE.** Delta-gap = -0.0425, 95% paired-bootstrap CI [-0.0975, +0.0125] over 10000 resamples of 80 profile ids. gap(n=232) = +0.0475 against gap(n=80) = +0.0900. The CI INCLUDES zero.
- **`gbt_tuned`: FLAT / INCONCLUSIVE.** Delta-gap = +0.0025, 95% paired-bootstrap CI [-0.0800, +0.0850] over 10000 resamples of 80 profile ids. gap(n=232) = +0.0275 against gap(n=80) = +0.0250. The CI INCLUDES zero.

**What these intervals cover**, stated because it is easy to assume more: profile
sampling variability *conditional on the seeds drawn*. They do NOT fold in seed
variability -- a two-way bootstrap over 5 seeds would be
hopelessly underpowered on the seed dimension -- and, as noted below, they do not fold
in subsample variability either. The per-seed results are therefore reported as a
table rather than summarised into them. The `+/-` in every top-2 column above is the
standard deviation across those 5 seeds, not a confidence
interval.

| point | seed | top-2 curve_nn | top-2 logistic_tuned | top-2 gbt_tuned |
|---|---|---|---|---|
| n=80 | 42 | 0.600 | 0.762 | 0.675 |
| n=80 | 43 | 0.637 | 0.750 | 0.688 |
| n=80 | 44 | 0.650 | 0.713 | 0.662 |
| n=80 | 45 | 0.625 | 0.713 | 0.625 |
| n=80 | 46 | 0.662 | 0.688 | 0.650 |
| n=232 | 42 | 0.823 | 0.875 | 0.879 |
| n=232 | 43 | 0.823 | 0.849 | 0.862 |
| n=232 | 44 | 0.828 | 0.828 | 0.871 |
| n=232 | 45 | 0.823 | 0.841 | 0.849 |
| n=232 | 46 | 0.802 | 0.858 | 0.871 |

**Verdict: the gap is flat / inconclusive against both comparators.**

Read as: **at these sizes, more data of this kind is not measurably closing the gap.** That is the more actionable outcome of the two for the question this curve was funded to answer -- it is evidence against buying more labels of the same kind as a way to close the distance to the comparators, and it is NOT evidence that the gap is fixed, because an interval covering zero covers useful narrowing as well as none.

## The balance-controlled control curve

Uniform 4 and 5 rows
per class, so balance is held FIXED at a skew of 1.0 while n moves. `game-dev`'s
5 labels cap uniform balance at n=80,
and k=3 is dropped for the same
protocol-floor reason n=48 is annotated -- which leaves
2 points.

| point | skew | max:min | n_val | top-2 curve_nn | top-2 logistic_tuned | top-2 gbt_tuned | gap vs logistic_tuned | gap vs gbt_tuned |
|---|---|---|---|---|---|---|---|---|
| uniform k=4 (n=64) | 1.00 | 4:4 | 16 | 0.550 +/- 0.029 | 0.684 +/- 0.050 | 0.628 +/- 0.050 | +0.1344 [+0.0750, +0.1969] | +0.0781 [+0.0063, +0.1469] |
| uniform k=5 (n=80) | 1.00 | 5:5 | 16 | 0.573 +/- 0.044 | 0.720 +/- 0.069 | 0.648 +/- 0.037 | +0.1475 [+0.0800, +0.2150] | +0.0750 [-0.0075, +0.1575] |

- `logistic_tuned`: gap +0.1344 at uniform k=4 (n=64) against +0.1475 at uniform k=5 (n=80), a move of +0.0131 -- and the main curve's Delta-gap is itself indistinguishable from zero ([-0.0975, +0.0125]), so comparing signs against it carries no information.
- `gbt_tuned`: gap +0.0781 at uniform k=4 (n=64) against +0.0750 at uniform k=5 (n=80), a move of -0.0031 -- and the main curve's Delta-gap is itself indistinguishable from zero ([-0.0800, +0.0850]), so comparing signs against it carries no information.

### The two n=80 points, which differ in balance and not in size

`n=80` and `uniform k=5 (n=80)` hold the same number of rows and differ in how those rows are
distributed across the careers -- and in which rows they are, since they are not
nested in each other. Comparing them isolates BALANCE at fixed n, which is
the thing the main curve cannot do -- and it exists by accident rather than design,
because `game-dev`'s label count happens to cap the uniform curve at the same n the
main curve's anchor point uses.

- `logistic_tuned`: gap +0.0900 at skew 3.67 against +0.1475 at skew 1.00 -- WIDER when the classes are made uniform.
- `gbt_tuned`: gap +0.0250 at skew 3.67 against +0.0750 at skew 1.00 -- WIDER when the classes are made uniform.

**Read this carefully, because it is easy to over-claim, and it carries no
interpretive weight beyond a sanity check** -- plan Step 2.6 bars the control curve
from carrying any, and this pair is made of control-curve data. The two points do not
share profiles, so this is not a paired comparison and no CI is computed across it.
More importantly the uniform point changes the TEST rows as well as the training rows:
top-2 agreement on a balanced test set is a harder measurement than on a skewed one,
because there is no dominant class to be right about by default. So a wider gap here
is partly a harder measurement and not only a harder training set. What it does bear on is the DIRECTION plan Step 2.6 assumed: it warned that better balance at small n might flatter the neural matcher and so manufacture an apparent narrowing. Here the gap is wider against both comparators when the classes are made uniform, which is the opposite direction -- so on this pair the confound is not working the way the warning anticipated.

**This is a two-point sanity check and it is barred from carrying trend weight.** Two
points cannot distinguish a trend from a pair of draws, no CI is computed on the
difference between them, and nothing in the verdict above rests on it. It is here to
show whether the direction survives when balance is not free to move with n, and a
direction is the most it can show.

## Disclosures, counted rather than argued

**The subsample is a function of the curve point alone and does not vary with the
experiment seed.** The seeds vary the 3-fold partition and the networks'
initialisation, as in Rounds 1 and 2. They do not vary which profiles are in a point,
because "the 80 profiles common to both points" is
one set only if every seed cuts the same subsample. **The cost: every number here is
conditional on ONE subsample draw at each point**, and the intervals no more fold in
subsample sampling variability than they fold in seed variability.

**The subsample ordering has a random tie-break, and here is what it decided.**
Classes with equally many surplus rows produce identical ordering keys, so a seeded
draw and not the key decides which of their rows falls inside a point. This applies
to the 5 MAIN-curve points only: the control curve takes a prefix of each
class separately, so no two classes' rows ever compete for the same slot there.
It decided membership at 1 of 5 points: n=116 (4 rows contested).

**What is not measured here.** No calibration number is reported: the pre-registered
reading is about top-2 gaps, ECE is not part of it, and the Ship Floor's calibration
verdict is DEV-95's and stands unchanged. Nothing here is Qualified, Selected,
Servable or Deployable, and nothing here reopens the search budget -- **there is still
no round 3**.

## What the curve does not answer

- Circularity is untouched. More labels of the same kind would move every number here
  and none of the validity concern; a Gold Slice is what addresses that, and it does
  not exist.
- Whether Round 2's unstable selection (8 Variants won contests and the top count was 7 of 25) is a sample-size
  effect. This curve is well placed to bear on that question and does not settle it:
  it measures how ONE frozen configuration's gap moves with n, not how the SELECTION
  moves with n, and those are different experiments.
- `MATCHER_MODEL_PATH` is untouched. That is DEV-99 and it is reserved for human
  approval.
