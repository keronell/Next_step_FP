# Neural Matcher Rework -- Round 2 and the FINAL Ship Floor verdict

> **All metrics are agreement with the synthetic LLM panel (silver labels), not
> expert-validated accuracy.** Circularity is untouched here and is a separate defect
> from Leakage: the labels reproduce the `careers.json` answer key, so every number
> below measures fidelity to a hand-authored bonus table. A second round of search
> does not make the labels less circular, and this one does not claim to.

DEV-95, plan `docs/dev-23-nn-rework-plan.md` Step 2.7. Ship Floor from ADR 0002, the
disqualification clause from ADR 0003. Vocabulary is `CONTEXT.md`'s.

Generated: 2026-07-30T16:37:40Z
Dataset: 232 rows, feature `features-v4`, digest `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`.
Experiment seeds: [42, 43, 44, 45, 46] -- identical to Round 1's.

## Summary

1. **Round 1's contest was re-run to recover the evidence it discarded.**
   `select_by_inner_cv` returned the argmax and dropped the other
   13 scores, so the ranking among the Variants that were never
   selected had been computed 25 times and thrown away
   25 times. DEV-95 added an additive out-channel and re-ran the
   14-way contest. **Every one of the 25 Round-1
   selections reproduced**.
2. **The best genuinely non-linear Variant is `C3_seed_ensemble`** at mean inner-CV
   top-2 0.7991 +/- 0.0236.
   That is the substitution ADR 0003 owed and Round 1 could not name. Its cost, paired
   per contest: the disqualified Residual Matcher scored on average
   +0.0280 above the best non-linear Variant on the selection metric,
   with the two level in 2 of 25 contests.
3. **Round 2 refined around that Variant, not around the Round-1 winner** -- the
   reinterpretation is stated in full below rather than applied quietly.
   6 refinements were evaluated under the identical protocol, folds and
   seeds. Result: a refinement was selected, and it is also the contest leader. The refinements took
   22 of 25 selections, so the second round earned its budget.
4. **Against the Incumbent `logistic_tuned`**, delta = -0.0181 on top-2,
   CI [-0.0440, +0.0060], sign holding in
   4 of 5 seeds. **Against
   `gbt_tuned`**, delta = -0.0440, sign holding in
   5 of 5.
5. **FINAL Ship Floor: the hard half clears, the mitigable half fails** at the gated partition -- top-2 stability
   0.735 (floor >= 0.6), raw ECE
   0.139 (floor <= 0.1). Across all 5
   experiment seeds stability clears in 5 of
   5 (mean 0.716 +/- 0.011) and
   raw ECE in 1 of 5.

**Verdict: `D5_ensemble_dropout_0.5_wd_1e-2` clears the hard stability floor but FAILS the mitigable ECE floor, so it may ship as the RANKING source with displayed percentages falling back to the formula's (ADR 0002).**

**THERE IS NO ROUND 3.** The budget was fixed in advance (plan Step 2.7) precisely so
that "keep tuning until it wins" is unavailable, and it is now spent.

## !! NOT A CONTINUATION OF ROUND 1's HEADLINE ROW !!

Round 1's selected model was the Residual Matcher, which collapsed to logistic
regression in 18 of 25 folds -- read back from
`round1_results.json` in this tree rather than transcribed. This round's candidate set **excludes** it, so the
`sweep_nn` column here describes a different set of eligible models. The two rounds
share their protocol, folds, seeds and comparators, and nothing else. Round 1's
numbers in `nn_rework.md` are unchanged and are not superseded by anything here.

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

## Why the Residual Matcher is not in this contest

ADR 0003 pre-registered that `alpha = 0` in >= 3 of 5 outer folds is "no non-linear
signal found" and **disqualifies the Residual Matcher from being the shipped neural
model**. Round 1 fired that rule in 4 of 5 seeds. A contest selects the model that
ships; entering a candidate that may not ship would produce a selection nobody could
honour, and would spend a third of this round's compute re-measuring a model whose
Round-1 numbers already stand.

This is the pre-registered rule executing, not a judgement made after seeing scores.
What is *not* discarded is its evidence: its per-contest counterfactual score is the
substitution cost reported below, computed from the same inner splits.

## The evidence Round 1 discarded

Re-running the 14-way contest with the out-channel open must not move a
single selection -- the contest is a pure function of `(X, y, tr, random_state)`, so a
selection that moved would mean either the channel is not inert or this is not Round
1's environment.

| seed | Round-1 selections reproduced? | folds differing |
|---|---|---|
| 42 | identical | 0 |
| 43 | identical | 0 |
| 44 | identical | 0 |
| 45 | identical | 0 |
| 46 | identical | 0 |

**All 25 selections are identical.**

### What every Variant actually scored

Mean inner-CV top-2 across all 25 (seed, outer fold) contests. `mean
rank` is carried beside the score because they answer different questions: a Variant
can hold a respectable mean while never coming close to winning a fold, and this table
is being read to choose between models that lost all 25 contests.

"Ranked first outright" counts contests a Variant won *alone*; ties are excluded from
it and take an average rank instead, so it can be smaller than the same Variant's
selection count -- the difference is exactly the contests registry order decided.

| Variant | axis | mean inner-CV top-2 | mean rank | ranked first outright |
|---|---|---|---|---|
| C4_residual_matcher | protocol | 0.8338 +/- 0.0201 | 1.04 | 23 of 25 |
| C3_seed_ensemble | protocol | 0.7991 +/- 0.0236 | 2.92 | 0 of 25 |
| B2_dropout_0.5 | regularization | 0.7828 +/- 0.0249 | 4.90 | 0 of 25 |
| B4_wd_1e-2 | regularization | 0.7782 +/- 0.0284 | 5.92 | 0 of 25 |
| C0_batch_16 | protocol | 0.7720 +/- 0.0310 | 7.18 | 0 of 25 |
| A3_84_64_16 | capacity | 0.7713 +/- 0.0221 | 7.32 | 0 of 25 |
| B5_input_noise_0.1 | regularization | 0.7707 +/- 0.0270 | 7.32 | 0 of 25 |
| B3_wd_1e-3 | regularization | 0.7662 +/- 0.0278 | 8.24 | 0 of 25 |
| A2_84_32_16 | capacity | 0.7655 +/- 0.0273 | 8.24 | 0 of 25 |
| V0_control | capacity | 0.7638 +/- 0.0289 | 8.82 | 0 of 25 |
| C1_full_batch | protocol | 0.7625 +/- 0.0308 | 9.14 | 0 of 25 |
| B1_dropout_0.1 | regularization | 0.7610 +/- 0.0311 | 9.14 | 0 of 25 |
| A1_84_16_16 | capacity | 0.7496 +/- 0.0252 | 10.82 | 0 of 25 |
| C2_sgd_cosine | protocol | 0.6545 +/- 0.0375 | 14.00 | 0 of 25 |

**The zero-selection Variants were not all equally beaten**, which is the finding
Round 1's selection counts could not express: a count of zero is the same number for a
Variant that was second in every fold and for one that was last in every fold.

### The cost of the substitution, paired per contest

ADR 0003 requires the cost of replacing the disqualified winner to be reported
explicitly. Measured on the selection metric, in the same contests:

- mean margin of the contest winner over the best genuinely non-linear Variant:
  **+0.0280** top-2
- worst single contest: +0.0702
- contests where the best non-linear Variant was level with the winner:
  2 of 25
- which Variant was the best non-linear one, per contest:
  A1_84_16_16 x1, A2_84_32_16 x1, A3_84_64_16 x1, B2_dropout_0.5 x3, B4_wd_1e-2 x3, C0_batch_16 x1, C1_full_batch x1, C3_seed_ensemble x14

### The same cost, priced on held-out top-2

The margin above is on the inner-CV selection metric. The quantity this deliverable
reports is pooled out-of-fold top-2, so the substitution is priced there too --
**exactly paired and refitting nothing**: both rounds ran seeds
42, 43, 44, 45, 46 over the same fold partitions, so the per-profile
indicators line up row for row.

- **delta (Round-2 selected minus Round-1 selected) = -0.0155** on top-2,
  95% paired-bootstrap CI [-0.0388, +0.0060] over
  10000 resamples of 232 profile ids. The CI
  INCLUDES zero.
- Per-seed deltas: +0.0000, -0.0431, -0.0043, +0.0000, -0.0302.
- Read as: obeying ADR 0003's disqualification costs
  3.6 profiles out of 232
  against the model Round 1 would have
  shipped.

**This is not the two rounds presented as a series.** It is the price of a candidate
set that excludes the Residual Matcher, measured against one that included it -- which
is precisely what ADR 0003 asks to be reported explicitly, and it is the reason the
"not a continuation" warning above forbids reading the `sweep_nn` columns as one model
improving rather than forbidding this comparison.

## The reinterpretation of "refinements around the round-1 best"

Plan Step 2.7 budgets "round 2 (<= 6 refinements around the round-1 best)". Read
literally that instruction no longer parses: **the round-1 best is the Residual
Matcher at `alpha = 0`, which is logistic regression** -- bit-identical to it, at a `C`
inherited from the same selection call `logistic_tuned` uses. Refining around it would
mean either tuning logistic regression, which is not a neural matcher and is not what
this step exists for, or widening the `alpha` grid, which ADR 0003 explicitly calls a
protocol change rather than a tuning tweak.

**The reading adopted here, stated rather than applied silently: refine around the
best genuinely non-linear Variant** -- `C3_seed_ensemble` -- because ADR 0003's
disqualification clause makes that the model which actually ships. "The round-1 best"
is read as "the best of the models still eligible to be the deliverable", which is the
only reading under which a refinement round has a purpose.

## The refinements

6 of the 6 the budget allows, fixed before this contest ran.

| refinement | axis | times selected | rationale |
|---|---|---|---|
| D1_ensemble_9 | protocol | 4 | 9 seed-averaged members instead of C3's 5 -- dose-response on the only mechanism Round 1 moved (+0.0353 over the same base) |
| D2_ensemble_dropout_0.5 | regularization | 7 | 5 members at dropout 0.5, the best-ranked pure MLP base (0.7828) |
| D3_ensemble_wd_1e-2 | regularization | 3 | 5 members at weight decay 1e-2, the second-best base (0.7782) and a different regularizer from D2's |
| D4_ensemble_84_64_16 | capacity | 0 | 5 members of the single-hidden-layer net (0.7713) -- ensembling under the plan's own hypothesis that V0 is too large for 232 rows |
| D5_ensemble_dropout_0.5_wd_1e-2 | regularization | 7 | 5 members combining the two best-ranked regularizers, neither of which was tried with the other in Round 1 |
| D6_dropout_0.5_wd_1e-2 | regularization | 1 | D5's configuration WITHOUT the ensemble -- the attribution control, so a D5 result is readable as the ensemble or as the combination, not both at once |

**None of them carries an internal search.** The Residual Matcher entered Round 1's
contest with a score that was a maximum over its four-point `alpha` grid, evaluated on
the ranking metric itself, while every other Variant contributed a single
configuration's score -- an optimism `nn_rework.md` reports in full. A refinement with
its own inner grid would inherit exactly that bias; none has one, so the Round-2
contest is a comparison of single draws throughout.

**The search budget this round spends.** Round 1's 14 Variants plus these
6 is 20 configurations, against
`gbt_tuned`'s 16-point nested grid and `logistic_tuned`'s
4. **The neural total is now ahead of the Incumbent's**, which
the plan flagged as a real cost of a second round and asked to be stated when it was
spent. This is that statement: "the NN was not tuned harder than the alternatives" was
true after Round 1 and is no longer true after Round 2.

## Round-2 contest results

19 Variants competed in every outer fold's inner 3-fold CV
-- 13 eligible Round-1 Variants plus 6
refinements.

| Variant | axis | times selected | round |
|---|---|---|---|
| D2_ensemble_dropout_0.5 | regularization | 7 | refinement |
| D5_ensemble_dropout_0.5_wd_1e-2 | regularization | 7 | refinement |
| D1_ensemble_9 | protocol | 4 | refinement |
| D3_ensemble_wd_1e-2 | regularization | 3 | refinement |
| A1_84_16_16 | capacity | 1 | round 1 |
| A2_84_32_16 | capacity | 1 | round 1 |
| B4_wd_1e-2 | regularization | 1 | round 1 |
| D6_dropout_0.5_wd_1e-2 | regularization | 1 | refinement |
| A3_84_64_16 | capacity | 0 | round 1 |
| B1_dropout_0.1 | regularization | 0 | round 1 |
| B2_dropout_0.5 | regularization | 0 | round 1 |
| B3_wd_1e-3 | regularization | 0 | round 1 |
| B5_input_noise_0.1 | regularization | 0 | round 1 |
| C0_batch_16 | protocol | 0 | round 1 |
| C1_full_batch | protocol | 0 | round 1 |
| C2_sgd_cosine | protocol | 0 | round 1 |
| C3_seed_ensemble | protocol | 0 | round 1 |
| D4_ensemble_84_64_16 | capacity | 0 | refinement |
| V0_control | capacity | 0 | round 1 |

**Selected: `D5_ensemble_dropout_0.5_wd_1e-2`.**

**That selection was a tie on count, broken on the metric.** 2 Variants each took 7 of 25 contests: `D5_ensemble_dropout_0.5_wd_1e-2` (0.8110 mean inner-CV top-2, 7 won outright) and `D2_ensemble_dropout_0.5` (0.8065, 4 outright). Resolved by mean inner-CV top-2 over all contests (the contest's own metric) -- because the alternative is letting declaration order in a Python dict decide which model DEV-97 exports. No rule for aggregating per-fold winners into one configuration was pre-registered, so this resolves a tie rather than moving a threshold, and **every Variant in the tie is Ship-Floor-scored below** so the choice hides nothing.

**The registry-order tie-break, and it reached the selected Variant.** `select_by_inner_cv`
keeps the first strictly-better score, so an exact tie goes to whichever Variant is
declared earlier -- and the refinements are declared after Round 1's Variants, with
`D1` before `D2` before `D3` and so on. At roughly
62 rows per
inner-validation split a single profile moves inner-CV top-2 by about
0.016, so ties are
common rather than exotic. **5 of
25 contests were decided by it**, between these groups:
D2_ensemble_dropout_0.5 = D5_ensemble_dropout_0.5_wd_1e-2; D2_ensemble_dropout_0.5 = D3_ensemble_wd_1e-2 = D5_ensemble_dropout_0.5_wd_1e-2; D2_ensemble_dropout_0.5 = D5_ensemble_dropout_0.5_wd_1e-2; A1_84_16_16 = D2_ensemble_dropout_0.5 = D4_ensemble_84_64_16 = D5_ensemble_dropout_0.5_wd_1e-2; D1_ensemble_9 = D4_ensemble_84_64_16.

`D5_ensemble_dropout_0.5_wd_1e-2` appears in a tied group above, so **the record cannot distinguish a tie-broken pick from a decisive one** for those contests. `nn_rework.md` could disclose this same bias and then show it decided nothing, because the Variants registry order favours won zero selections in Round 1. That reassurance is a property of Round 1's counts and is not repeated here.

### What every Variant scored in the Round-2 contest

| Variant | axis | mean inner-CV top-2 | mean rank | ranked first outright |
|---|---|---|---|---|
| D5_ensemble_dropout_0.5_wd_1e-2 | regularization | 0.8110 +/- 0.0204 | 2.92 | 7 of 25 |
| D2_ensemble_dropout_0.5 | regularization | 0.8065 +/- 0.0203 | 3.96 | 4 of 25 |
| D3_ensemble_wd_1e-2 | regularization | 0.8052 +/- 0.0213 | 4.04 | 3 of 25 |
| D1_ensemble_9 | protocol | 0.8019 +/- 0.0248 | 4.90 | 3 of 25 |
| C3_seed_ensemble | protocol | 0.7991 +/- 0.0236 | 5.44 | 0 of 25 |
| D4_ensemble_84_64_16 | capacity | 0.7935 +/- 0.0232 | 6.98 | 0 of 25 |
| D6_dropout_0.5_wd_1e-2 | regularization | 0.7873 +/- 0.0224 | 7.40 | 1 of 25 |
| B2_dropout_0.5 | regularization | 0.7828 +/- 0.0249 | 8.80 | 0 of 25 |
| B4_wd_1e-2 | regularization | 0.7782 +/- 0.0284 | 9.80 | 1 of 25 |
| C0_batch_16 | protocol | 0.7720 +/- 0.0310 | 11.30 | 0 of 25 |
| A3_84_64_16 | capacity | 0.7713 +/- 0.0221 | 11.74 | 0 of 25 |
| B5_input_noise_0.1 | regularization | 0.7707 +/- 0.0270 | 11.82 | 0 of 25 |
| B3_wd_1e-3 | regularization | 0.7662 +/- 0.0278 | 13.04 | 0 of 25 |
| A2_84_32_16 | capacity | 0.7655 +/- 0.0273 | 12.70 | 1 of 25 |
| V0_control | capacity | 0.7638 +/- 0.0289 | 13.50 | 0 of 25 |
| C1_full_batch | protocol | 0.7625 +/- 0.0308 | 13.42 | 0 of 25 |
| B1_dropout_0.1 | regularization | 0.7610 +/- 0.0311 | 13.66 | 0 of 25 |
| A1_84_16_16 | capacity | 0.7496 +/- 0.0252 | 15.58 | 0 of 25 |
| C2_sgd_cosine | protocol | 0.6545 +/- 0.0375 | 19.00 | 0 of 25 |

Best by mean inner-CV score: `D5_ensemble_dropout_0.5_wd_1e-2`, which is
a refinement.
Against the Variant the refinements were built around (`C3_seed_ensemble`) that is a
change of +0.0118 on the selection metric.

### What the attribution control shows

`D6_dropout_0.5_wd_1e-2` is `D5_ensemble_dropout_0.5_wd_1e-2`'s configuration without the ensemble -- the same
dropout, the same weight decay, one network instead of five. It scored
0.7873 against 0.8110,
so **seed-averaging is worth +0.0237 here**, holding the regularization fixed.

Round 1 supplies the same measurement on a different base: `C3_seed_ensemble` against
the `V0_control` it ensembles, +0.0353. Two exactly paired comparisons on
two different bases, agreeing in sign, are what let this round attribute its result to
seed-averaging rather than to the regularizers it was combined with. Round 1 could not
make that attribution at all, because it recorded only which Variant won.

## Per-seed results

Each row is a complete nested run on the same folds for all three models. **The ECE
columns are CROSS-FITTED** (ADR 0004) -- a different quantity from the raw ECE the
Ship Floor gates on. Do not read across the two tables.

| seed | top-2 selected | top-2 logistic | top-2 gbt | x-fit ECE selected | x-fit ECE logistic | x-fit ECE gbt |
|---|---|---|---|---|---|---|
| 42 | 0.832 | 0.849 | 0.892 | 0.101 | 0.061 | 0.040 |
| 43 | 0.823 | 0.871 | 0.879 | 0.054 | 0.049 | 0.053 |
| 44 | 0.836 | 0.841 | 0.879 | 0.077 | 0.056 | 0.059 |
| 45 | 0.858 | 0.858 | 0.871 | 0.034 | 0.041 | 0.038 |
| 46 | 0.845 | 0.866 | 0.892 | 0.057 | 0.066 | 0.041 |
| **mean +/- sd** | 0.839 +/- 0.012 | 0.857 +/- 0.011 | 0.883 +/- 0.008 | 0.065 +/- 0.023 | 0.055 +/- 0.009 | 0.046 +/- 0.008 |

**The comparator legs are Round 1's, reused rather than refitted.** `gbt_tuned` and
`logistic_tuned` do not depend on the Variant registry, and within a seed the fold
partition is a function of the seed alone, so their Round-2 numbers *are* their
Round-1 numbers. Reused is not the same as assumed: seed
42 was recomputed from scratch and compared per
profile -- identical in both models, 0 of 232 profiles disagreeing.

## Effect size (Step 2.5)

**The sampling unit is the PROFILE.** Each profile's top-2 hit indicator is averaged
across the 5 seeds first, then differenced, and the bootstrap then resamples
the 232 profile ids. The interval covers profile sampling variability
*conditional on the seeds drawn*; it does not fold in seed variability, which is why
the per-seed table above is reported separately rather than summarised into it.

### Against `logistic_tuned`

- **delta (top-2, Round-2 selected minus logistic_tuned) = -0.0181**, 95%
  paired-bootstrap CI [-0.0440, +0.0060] over 10000
  resamples of 232 profile ids.
- The CI INCLUDES zero.
- Materiality marker (Step 2.5, |delta| >= 0.02): **not cleared**
  (|delta| = 0.0181). A reporting standard, not a gate: under ADR 0001
  the neural matcher ships either way, so this sizes the gap rather than authorising
  anything.
- Per-seed deltas: -0.0172, -0.0474, -0.0043, +0.0000, -0.0216.
  The pooled sign holds in **4 of 5** seeds,
  so it IS stable under the >= 3-of-5 rule.
- Read as: the Round-2 selected model is behind `logistic_tuned` by
  4.2 profiles out of 232.

### Against `gbt_tuned`

- **delta (top-2, Round-2 selected minus gbt_tuned) = -0.0440**, 95%
  paired-bootstrap CI [-0.0750, -0.0138] over 10000
  resamples of 232 profile ids.
- The CI EXCLUDES zero.
- Materiality marker (Step 2.5, |delta| >= 0.02): **cleared**
  (|delta| = 0.0440). A reporting standard, not a gate: under ADR 0001
  the neural matcher ships either way, so this sizes the gap rather than authorising
  anything.
- Per-seed deltas: -0.0603, -0.0560, -0.0431, -0.0129, -0.0474.
  The pooled sign holds in **5 of 5** seeds,
  so it IS stable under the >= 3-of-5 rule.
- Read as: the Round-2 selected model is behind `gbt_tuned` by
  10.2 profiles out of 232.

## FINAL Ship Floor verdict (Step 2.7 / ADR 0002)

Evaluated on **one exact configuration** -- `D5_ensemble_dropout_0.5_wd_1e-2` -- because
Qualified is a property of a configuration and is never inherited by a reconfigured
model (`CONTEXT.md`). Round 1's Ship Floor numbers describe a different configuration
and transfer nothing to this one.

**How dominant that configuration is, stated because it bears on what "selected"
means here.** `D5_ensemble_dropout_0.5_wd_1e-2` took
7 of 25 selections
(28%), against Round 1's modal Variant at
23 of 25 (92%). **That is a minority of the contests, and it qualifies what this round selected.** The protocol did not converge on one configuration: it chose 8 different Variants across the contests, and the Ship Floor below is evaluated on the most frequent of them. Read `D5_ensemble_dropout_0.5_wd_1e-2` as the modal answer of an unstable selection, not as a configuration the evidence singled out -- a real finding about what n=232 can resolve, and one the decision document should carry.

**The determinism assertion passed before any stability number was computed**
(passed). `assert_deterministic` raises rather than returning
a flag, so there is no code path that produces a stability number without it.

| half | value | floor | clears? | mitigable? |
|---|---|---|---|---|
| top-2 stability | 0.735 | >= 0.6 | YES | no -- hard and unmitigable |
| **raw** ECE | 0.139 | <= 0.1 | **NO** | yes -- may ship as ranking source with formula percentages |

### Both halves under all 5 experiment seeds

Reported beside the gated verdict, never substituted for it: Gate 1's convention is one
fixed partition, and switching the gate to a 5-seed mean after seeing the data would be
moving a threshold rather than tightening one.

| seed | top-2 stability | clears >= 0.6? | raw ECE | clears <= 0.1? |
|---|---|---|---|---|
| 42 | 0.735 | yes | 0.139 | **NO** |
| 43 | 0.706 | yes | 0.120 | **NO** |
| 44 | 0.718 | yes | 0.140 | **NO** |
| 45 | 0.718 | yes | 0.098 | yes |
| 46 | 0.703 | yes | 0.107 | **NO** |

Stability mean 0.716 +/- 0.011, minimum
0.703; **5 of 5 seeds
clear the hard floor**. Raw ECE mean 0.121 +/- 0.017,
maximum 0.140; **1 of 5 clear the
mitigable one**.

**Failing the ECE floor is the common case for this configuration, not the gated partition's peculiarity.** 4 of 5 partitions fail it. Round 1's modal Variant cleared on 4 of 5, so its gated failure was a partition effect and reading it as 'this model is miscalibrated' would have been wrong. That defence is not available here: the mitigation is what makes this model shippable, not an argument that the number is unrepresentative.

For reference, the Incumbent `logistic` clears both -- read back from
`gate1_verdict.json` in this tree rather than transcribed: ECE
0.0341, stability
0.6375. So the floor is known achievable
on this data.


### The other arm of the selection-count tie, on the same floor

Scored because a tie-break that is only disclosed, and not priced, still leaves the
reader unable to see what it decided.

| configuration | stability (gated) | clears? | raw ECE (gated) | clears? | stability across seeds | ECE across seeds |
|---|---|---|---|---|---|---|
| `D5_ensemble_dropout_0.5_wd_1e-2` (selected) | 0.735 | yes | 0.139 | **NO** | 5 of 5 | 1 of 5 |
| `D2_ensemble_dropout_0.5` | 0.726 | yes | 0.140 | **NO** | 5 of 5 | 0 of 5 |

**Both arms of the tie reach the same Ship Floor verdict**, so the tie-break moved which configuration ships but not whether one could.

### Against the recorded neural Gate-1 row

`gate1_verdict.json`'s `small_nn` entry is the V0 configuration measured by the same
`cv_oof_and_stability` call, on the same default partition and the same inner splits,
so it is directly comparable to the gated row above -- the two differ in the estimator
and in nothing else.

| configuration | raw ECE | top-2 stability |
|---|---|---|
| `small_nn` (V0), recorded Gate 1 | 0.0618 | 0.6153 |
| `D5_ensemble_dropout_0.5_wd_1e-2`, this round | 0.1392 | 0.7346 |

Stability moves by +0.1193
and raw ECE by +0.0774. Qualified is
never inherited across configurations (`CONTEXT.md`), so this comparison sizes a
change rather than transferring a verdict -- the gated row above is what qualifies or
does not qualify `D5_ensemble_dropout_0.5_wd_1e-2`.

## The final selected configuration, in full

DEV-97 exports this. A Variant name is not a specification, so every hyperparameter is
recorded -- read from the constructor's signature rather than transcribed, defaults
included.

| field | value |
|---|---|
| class | `nn_model.SeedEnsemble` |
| n_members | `5` |
| member | `{'class': 'nn_model.NNClassifier', 'hidden_sizes': [64, 32], 'dropout': 0.5, 'lr': 0.001, 'weight_decay': 0.01, 'batch_size': 32, 'max_epochs': 400, 'patience': 30, 'val_fraction': 0.15, 'input_noise': 0.0, 'optimizer': 'adam', 'lr_schedule': None, 'momentum': 0.9}` |
| member_seeds | `random_state + i for i in range(n_members)` |
| axis | `regularization` |
| random_state | `42` |

Rationale: 5 members combining the two best-ranked regularizers, neither of which was tried with the other in Round 1

**This is 5 networks, not one, and DEV-97 inherits that.** The artifact carries every member and serve-time inference runs all 5 forward passes before averaging in probability. Explainability is unaffected: integrated gradients is linear in the model function, so attribution over a probability-averaged ensemble is the average of the members' attributions (plan Step 2.2). The cost is artifact size and serve-time compute, and it is a real cost that the decision document should name rather than discover.

## What Round 2 does not answer

- Circularity is untouched. Every number here is agreement with silver labels that
  reproduce the `careers.json` answer key.
- Nothing here is Servable or Deployable. The serving path (`matcher_nn.py`), the
  export (`export_nn_model.py`), the learning curve and the decision document are
  separate tickets, and Gate-1 revalidation of the exact exported artifact is part of
  the export, not of this round.
- `MATCHER_MODEL_PATH` is untouched. The shipped artifact's temperature is 1.05, not
  1.0, and DEV-88 made the serving path divide logits by that field in both
  `predict_proba` and `contributions` -- so flipping the flag changes served
  `matchPercent`. Ranking is unaffected: temperature scaling is monotone within a row.
