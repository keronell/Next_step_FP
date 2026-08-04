# Neural Matcher Rework -- Round 1

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Circularity is untouched here and is a separate
> defect from Leakage: the labels reproduce the `careers.json` answer key, so every
> number below measures fidelity to a hand-authored bonus table. A better protocol
> does not make the labels less circular, and this one does not claim to.

DEV-93, plan `docs/dev-23-nn-rework-plan.md` Steps 2.2 / 2.4 / 2.5 / 2.7. Ship
Floor from ADR 0005. Vocabulary is `CONTEXT.md`'s.

Generated: 2026-07-29T17:02:30Z
Dataset: 232 rows, feature `features-v4`, digest `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`.
Experiment seeds: [42, 43, 44, 45, 46].

## Summary

Round 1's result is **negative, and cleanly so**.

1. **18 of 25 (seed, outer fold) selections resolved to the
   Residual Matcher at `alpha = 0`**, which is *exactly* logistic regression. The
   12 pure-MLP Variants -- every capacity and every regularization Variant, the
   three non-ensemble protocol ones, and the control V0 that the recorded `small_nn`
   numbers came from -- were selected **0 times between them**.
2. **The pre-registered alpha=0 rule fires**, having fired in
   4 of 5 seeds: "no non-linear signal
   found". The Residual Matcher is therefore disqualified from being the shipped
   neural model, per ADR 0006.
3. **Against `logistic_tuned` the difference is indistinguishable from zero.** delta =
   -0.0026 on top-2, CI [-0.0095, +0.0043],
   sign holding in 2 of 5 seeds.
   That is expected rather than surprising: for most folds the two are the same
   estimator.
4. **Against `gbt_tuned` the selected Variant is behind it**, delta =
   -0.0284, and the sign is stable across seeds
   (5 of 5) --
   though the profile-level interval still includes zero [-0.0595, +0.0026]. Per-seed
   consistency and the interval can disagree in flavour, which is exactly why both
   are reported rather than one summarised into the other.
5. **Ship Floor: the hard half clears, the mitigable half fails** at the gated partition -- top-2 stability
   0.655 (floor >= 0.6), raw ECE
   0.122 (floor <= 0.1). Re-measured across all
   5 experiment seeds, **stability clears in
   5 of 5** (mean
   0.666 +/- 0.009) while **ECE clears in
   4 of 5**, so the two halves are not equally
   solid and the ECE verdict in particular is partition-sensitive. The ECE figure is
   the *raw* one Gate 1 gates on -- a different quantity from the cross-fitted ECE in
   the per-seed table. What drives it is the inherited regularization strength and
   the fold partition, not neural capacity, of which the evaluated configuration has
   none.

**What this does NOT say.** It does not say a neural matcher cannot clear the floor;
Round 2 has not run. It does not say the labels are sound -- Circularity is untouched.
And it does not authorise any decision: under ADR 0004 the neural matcher ships
either way, so these numbers size a gap rather than settle anything.

## !! NOT A CONTINUATION OF THE DEV-91 GATE-2 ROW !!

Everything here is produced by a **5-seed protocol**, where each experiment seed is
a complete nested run varying both the fold partition and the initialisation. The
DEV-91 Gate-2 numbers (`gbt_tuned` 0.892, `logistic_tuned` 0.849, `small_nn` 0.845,
`two_tower` 0.763) come from a single seed on one fixed partition. **These are a
different measurement, not a later reading of the same one**, and the two must not
be presented as a series.

A second reason the control is not the Gate-2 `small_nn` row: this sweep trains on
**hard labels** throughout, while Gate 2's `small_nn` additionally consumes the
panel vote distribution as soft targets. The control Variant here is the *Gate-1*
`small_nn` configuration.

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

## Protocol

**All 14 Variants compete inside every outer fold's inner
3-fold CV.** There is no separate selection stage, therefore no stage
that can leak. An earlier revision scored Variants on the outer-fold-1 training
partition -- which under 5-fold CV is precisely the union of the test sets of
folds 2-5, so selection would have seen 100% of the evaluation data for four of
five folds. That pass is deleted, not fixed.

**How much search this is, stated accurately.** `gbt_tuned` selects from a
16-point grid nested in every outer fold and `logistic_tuned` from
4. The NN's 14-point nested grid is therefore
**comparable** to what the tuned GBT already gets
(14 against 16), and wider than the logistic one.

That still defeats "the sweep was tuned harder than the Incumbent" -- it was not -- but
it does **not** support a claim of restraint. Rev 3 of the plan claimed a "32-point"
GBT grid, which would have made this a fraction of the Incumbent's search;
`GBT_GRID` is a `product` of four 2-element lists, so it is 16, and
the argument was overstated by 2x. Corrected in the plan and stated honestly here.

**Seeds sit outside selection.** Inner CV runs single-seed. Within a seed all three
models share outer folds, so the per-profile indicators are genuinely paired.

### The Residual Matcher's advantage in this contest, stated properly

ADR 0006 pre-registered `alpha` as an inner-CV-selected hyperparameter, so before
the 14-way contest the Residual Matcher resolves `(alpha, C)` on the
outer-training partition -- `alpha` by argmax over
4 values, on top of a `C` itself chosen by argmax over
4.

**That resolution uses the same inner splits that then rank all 14
Variants** -- same `tr`, same `random_state`, therefore the same
`StratifiedKFold`. So the Residual Matcher enters the contest carrying a score that
is a *maximum over 4 configurations* on the ranking
metric itself, while each pure-MLP Variant contributes a single configuration's
score. A maximum over several draws beats a single draw on average even when
nothing differs between them, so **the Residual Matcher's inner-CV score is
optimistically biased relative to its competitors, and the selection counts below
must be read with that in mind.** Calling it merely "one extra search" would
understate it.

This is **not Leakage** in `CONTEXT.md`'s sense -- no held-out row is touched at any
point, and `test_variant_selection.py` pins that. It is selection optimism inside
the training partition, which costs the contest its fairness between Variants but
not the outer estimate its validity.

It is left in place rather than fixed because removing it means selecting `alpha` at
a third nesting level, which ADR 0006 explicitly considered and declined as not
earning its complexity. **What the bias does not do is change the direction of the
finding**, and that is worth being precise about: the Residual Matcher won mostly
*at `alpha = 0`*, so the extra freedom it enjoyed was the freedom to switch its
neural branch off. A biased contest that hands victory to the degenerate member of
the biased Variant's own grid is not evidence of non-linear signal being
over-credited; it is the same negative finding arriving by a second route.

## Which Variant won

Across all 5 seeds x 5 outer folds = 25 selections:

| Variant | axis | times selected | specification |
|---|---|---|---|
| C4_residual_matcher | protocol | 23 | frozen logistic branch plus a gated MLP correction; alpha selected by inner CV, C inherited from the fold's tuned-logistic selection (ADR 0006) |
| C3_seed_ensemble | protocol | 2 | 5 members differing only in seed, averaged in probability; a separate Variant, never fused into the Residual Matcher |
| A1_84_16_16 | capacity | 0 | one hidden layer of 16 -- the smallest net that still has a hidden layer |
| A2_84_32_16 | capacity | 0 | one hidden layer of 32 |
| A3_84_64_16 | capacity | 0 | one hidden layer of 64 -- V0's width without V0's depth |
| B1_dropout_0.1 | regularization | 0 | less dropout than V0's 0.3 |
| B2_dropout_0.5 | regularization | 0 | more dropout than V0's 0.3 |
| B3_wd_1e-3 | regularization | 0 | 10x V0's weight decay |
| B4_wd_1e-2 | regularization | 0 | 100x V0's weight decay |
| B5_input_noise_0.1 | regularization | 0 | Gaussian input noise sigma=0.1 on standardized features, training only |
| C0_batch_16 | protocol | 0 | half V0's batch size -- more gradient steps per epoch at n=232 |
| C1_full_batch | protocol | 0 | one gradient step per epoch; no minibatch noise at all |
| C2_sgd_cosine | protocol | 0 | SGD+momentum 0.9 with a cosine learning-rate schedule instead of Adam |
| V0_control | capacity | 0 | V0: the configuration small_nn's recorded Gate-1 and Gate-2 numbers came from, entered as the control (plan Step 2.2, A4) |

**Modal Variant: `C4_residual_matcher`** at (alpha, C) = (0.0, 0.25).

**Caveat on that table: ties are broken by registry order.** `select_by_inner_cv`
keeps the first strictly-better score, so two Variants tying on inner-CV top-2
resolve to whichever is declared earlier -- and the registry declares the capacity
axis first, so ties resolve toward the LOWER-CAPACITY Variants. At n=232, an
outer training partition holds about 186 rows
and each inner-validation split about
62 of them, so a
single profile moves inner-CV top-2 by roughly
0.016 and exact ties
are common rather than exotic. The record
above cannot distinguish a tie-broken pick from a decisive one. The order was fixed
before any data was seen and is a defensible default under this plan's own
hypothesis -- that the current net is too large for 232 rows -- but it is a thumb on
the scale and it is disclosed rather than buried.

**In this run the tie-break favoured Variants that won nothing.** It advantages the
earliest-declared Variants, the four capacity ones, and they were selected
0
times out of 25. So tie-breaking cannot be what kept them out of the
counts -- it was pushing the other way.

Note that the two biases in this contest point in **opposite** directions: registry
order favours the low-capacity MLP Variants, while the argmax-over-alpha described
above favours the Residual Matcher. Only the second one had any effect on the
outcome. This is a weaker statement than "the winning Variant beat the others
outright", which an earlier draft of this report made and which the alpha argmax
does not support.

## How much of this "neural matcher" is a neural network?

**This is the central finding of Round 1 and it is a negative one.** At `alpha = 0`
the Residual Matcher's predictions are bit-identical to `frozen_logistic` at the
same `C`, and the sweep inherits `C` from the same `select_by_inner_cv` call
`logistic_tuned` uses -- so in those folds the two are *the same estimator*, not
merely similar ones.

| seed | folds collapsed to logistic | profiles where the sweep NN differs from `logistic_tuned` |
|---|---|---|
| 42 | 4 of 5 | 4 of 232 |
| 43 | 4 of 5 | 1 of 232 |
| 44 | 2 of 5 | 4 of 232 |
| 45 | 5 of 5 | 0 of 232 |
| 46 | 3 of 5 | 6 of 232 |

**18 of
25 outer-fold selections resolved to exactly
logistic regression.** The row-disagreement column is the observable consequence:
the model Round 1 selected makes the same top-2 recommendation as the Incumbent for
all but a handful of the 232 profiles, and in at least one seed for
every single one of them.

Read the effect-size section below with that in mind. A delta of
-0.0026 against `logistic_tuned` is not
evidence that a neural matcher performs comparably to logistic regression; it is
mostly the measurement of a model that *is* logistic regression, compared against
itself.

## Per-seed results

Each row is a complete nested run. `mean +/- sd` is meaningful for the two
comparators too, not only for the selected Variant, because the seed varies the fold
partition for all three.

**The ECE columns here are CROSS-FITTED** (ADR 0007), which is a different quantity
from the raw ECE the Ship Floor gates on. Do not read across the two tables.

| seed | top-2 selected | top-2 logistic | top-2 gbt | x-fit ECE selected | x-fit ECE logistic | x-fit ECE gbt |
|---|---|---|---|---|---|---|
| 42 | 0.832 | 0.849 | 0.892 | 0.061 | 0.061 | 0.040 |
| 43 | 0.866 | 0.871 | 0.879 | 0.044 | 0.049 | 0.053 |
| 44 | 0.841 | 0.841 | 0.879 | 0.045 | 0.056 | 0.059 |
| 45 | 0.858 | 0.858 | 0.871 | 0.041 | 0.041 | 0.038 |
| 46 | 0.875 | 0.866 | 0.892 | 0.081 | 0.066 | 0.041 |
| **mean +/- sd** | 0.854 +/- 0.016 | 0.857 +/- 0.011 | 0.883 +/- 0.008 | 0.054 +/- 0.015 | 0.055 +/- 0.009 | 0.046 +/- 0.008 |

## Effect size (Step 2.5)

**The sampling unit is the PROFILE.** Each profile's top-2 hit indicator is averaged
across the 5 seeds first, then differenced, and the bootstrap then resamples the
232 profile ids. Treating the 1160 profile-seed rows
as independent would understate the standard error by about sqrt(5) = 2.2x
and silently narrow every interval below.

**What these intervals cover:** profile sampling variability *conditional on the
seeds drawn*. They do NOT fold in seed variability -- a two-way bootstrap over
5 seeds would be hopelessly underpowered on the seed dimension -- which is why
the per-seed table above is reported separately rather than summarised into them.

### Against `logistic_tuned`

- **delta (top-2, sweep NN minus logistic_tuned) = -0.0026**, 95% paired-bootstrap
  CI [-0.0095, +0.0043] over 10000 resamples of
  232 profile ids.
- The CI INCLUDES zero.
- Materiality marker (Step 2.5, |delta| >= 0.02): **not cleared**
  (|delta| = 0.0026). This is a reporting standard, not a gate: under
  ADR 0004 the neural matcher ships either way, so nothing here authorises a
  decision -- it sizes the gap.
- Per-seed deltas: -0.0172, -0.0043, +0.0000, +0.0000, +0.0086.
  The pooled sign holds in **2 of 5** seeds,
  so it is NOT stable under the >= 3-of-5 rule.
- Read as: the sweep NN is behind `logistic_tuned` by
  0.6 profiles out of 232.

### Against `gbt_tuned`

- **delta (top-2, sweep NN minus gbt_tuned) = -0.0284**, 95% paired-bootstrap
  CI [-0.0595, +0.0026] over 10000 resamples of
  232 profile ids.
- The CI INCLUDES zero.
- Materiality marker (Step 2.5, |delta| >= 0.02): **cleared**
  (|delta| = 0.0284). This is a reporting standard, not a gate: under
  ADR 0004 the neural matcher ships either way, so nothing here authorises a
  decision -- it sizes the gap.
- Per-seed deltas: -0.0603, -0.0129, -0.0388, -0.0129, -0.0172.
  The pooled sign holds in **5 of 5** seeds,
  so it IS stable under the >= 3-of-5 rule.
- Read as: the sweep NN is behind `gbt_tuned` by
  6.6 profiles out of 232.

## Ship Floor verdict (Step 2.7 / ADR 0005)

Evaluated on **one exact configuration** -- the modal Variant `C4_residual_matcher`
-- because Qualified is a property of a configuration and is never inherited by a
reconfigured model (`CONTEXT.md`).

**The determinism assertion passed before any stability number was computed**
(passed). That ordering is enforced in
`evaluate_ship_floor`, not remembered: `assert_deterministic` raises rather than
returning a flag, so the hard floor cannot fire on a measurement artifact.

| half | value | floor | clears? | mitigable? |
|---|---|---|---|---|
| top-2 stability | 0.655 | >= 0.6 | YES | no -- hard and unmitigable |
| **raw** ECE | 0.122 | <= 0.1 | **NO** | yes -- may ship as ranking source with formula percentages |

### The hard floor under all 5 experiment seeds

The verdict above is the Gate-1 convention: one fixed partition, seed
42. But the stability half is **hard and unmitigable** --
failing it escalates as a project-level finding rather than degrading into anything
-- while every other number in this deliverable is a 5-seed measurement. A hard
threshold resting on one draw deserves the same treatment, so it is re-measured
here. **This is reported beside the gated number, not substituted for it**;
switching the gate to a 5-seed mean after seeing the data would be moving a
threshold, not tightening one.

| seed | top-2 stability | clears >= 0.6? | raw ECE |
|---|---|---|---|
| 42 | 0.655 | yes | 0.122 |
| 43 | 0.662 | yes | 0.097 |
| 44 | 0.681 | yes | 0.096 |
| 45 | 0.659 | yes | 0.100 |
| 46 | 0.670 | yes | 0.084 |

Stability mean 0.666 +/- 0.009, minimum
0.655. **5 of 5
seeds clear the hard floor.**
The margin is not an artifact of the partition that happened to be gated.

**The mitigable half behaves differently, and this qualifies the verdict above.**
Raw ECE ranges 0.084 to
0.122 across the same partitions (mean 0.100 +/-
0.012), and **4 of 5 seeds clear
the <= 0.1 floor**.
So the ECE failure recorded in the verdict above is specific to the gated partition rather than a property of the configuration: on most fold partitions this same model clears the floor. The gated number is not wrong -- Gate 1's convention is one fixed partition and changing it after the fact would be moving a threshold -- but reading it as 'this model is miscalibrated' would be. Combined with the C-sensitivity table below, the honest summary is that raw ECE here is governed by the inherited regularization strength and the fold partition, neither of which is a neural property.

### Two different ECEs, and they are not comparable

The per-seed table above prints **cross-fitted** ECE (mean
0.054); the row
above prints **raw** ECE (0.122). Both are honest and they measure
different things, so the same model can look calibrated in one table and fail in the
other. Gate 1 has never applied a temperature and gates on the raw number (ADR
0004), which is why the floor uses it. Stated explicitly because a reader who
carries 0.122 back into the per-seed table, or the reverse, will reach a
conclusion neither number supports.

**Verdict: the modal Variant clears the hard stability floor but FAILS the mitigable ECE floor, so it may ship as the ranking source with displayed percentages falling back to the formula's.**

### The ECE verdict is a statement about `C`, not about neural capacity

The modal configuration is the Residual Matcher at `alpha = 0`, so it contributed
**no neural parameters to the number above**: it is logistic regression at the `C`
its folds most often inherited. Raw ECE is strongly sensitive to that `C`, and inner
CV chose it inconsistently -- across the 25
outer folds every value in the grid was selected at least once.

| inherited C | raw ECE | clears <= 0.1? | top-2 stability | top-2 |
|---|---|---|---|---|
| 0.05 | 0.2898 | **NO** | 0.6879 | 0.8448 |
| 0.25 | 0.1216 | **NO** | 0.6548 | 0.8664 |
| 1.0 | 0.0341 | yes | 0.6375 | 0.8707 |
| 4.0 | 0.0983 | yes | 0.6251 | 0.8707 |

So the ECE floor is failed **at the modal `C`** and comfortably cleared at another
value of the same grid, by the identical estimator. Attributing that failure to the
neural architecture would be wrong: there is no neural architecture in it. The
honest reading is that `C` is unstable under this protocol and raw calibration
follows it.

For reference, the Incumbent `logistic` clears both -- read back from the
`gate1_verdict.json` in this tree rather than transcribed: ECE
0.0341, stability
0.6375. So the floor is known
achievable on this data.

## The pre-registered alpha=0 rule

The Residual Matcher leads Round 1. Its per-fold
alpha choices are reported either way -- whether a non-linear signal exists in these
features at all is what the rule measures, and a rule consulted only when it is
convenient is not a pre-registered rule. Inner CV resolved an alpha for it in every
outer fold, including folds where a different Variant went on to win the contest,
so the record below has no holes in it.

The rule, from ADR 0006, fixed before any alpha was selected on this data:

> alpha=0 in >= 3 of 5 outer folds is 'no non-linear signal found' and disqualifies the Residual Matcher from being the shipped neural model (ADR 0006, pre-registered)

| seed | per-fold alpha | folds at zero | rule |
|---|---|---|---|
| 42 | [0.0, 0.0, 0.0, 0.0, 0.0] | 5 | FIRED |
| 43 | [0.0, 1.0, 0.0, 0.0, 0.0] | 4 | FIRED |
| 44 | [0.0, 0.25, 0.0, 0.5, 0.5] | 2 | did not fire |
| 45 | [0.0, 0.0, 0.0, 0.0, 0.0] | 5 | FIRED |
| 46 | [0.5, 0.0, 0.0, 0.0, 0.0] | 4 | FIRED |

**The rule fired in 4 of 5 seeds**
(42, 43, 45, 46). A Residual Matcher disqualified
by this rule is still reported in full; what the rule decides is whether it may be
the shipped neural model, not whether its numbers count.

**The consequence, per the plan's Step 6 and ADR 0006:** if the rule stands, the
shipped model becomes the best *genuinely non-linear* Variant, and the cost of that
substitution must be reported explicitly. Round 1 does not make that substitution --
choosing the replacement is Round 2's job and justifying it is the decision
document's -- but the substitution is now owed, and its cost is a real one: every
non-collapsed Variant in the table above was selected less often than the collapsed
Residual Matcher, so the replacement will be a model this round's own protocol
ranked lower.

## What Round 1 does not answer

- Round 2 refinements, the learning curve, the serving path and the decision
  document are separate tickets. Nothing here is Selected, Servable or Deployable.
- `MATCHER_MODEL_PATH` is untouched. Note that the shipped artifact's temperature is
  no longer 1.0 (it is 1.05 since the DEV-91 export fix), and DEV-88 made the
  serving path divide logits by that field in both `predict_proba` and
  `contributions` -- so flipping the flag now changes served `matchPercent`. Earlier
  reports called that field inert; it is not.
