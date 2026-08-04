---
status: accepted
---

# Calibration temperature is cross-fitted, and Gate 2 history is re-baselined once

`temperature_scale()` fitted a single temperature on the pooled out-of-fold
predictions and then scored ECE on those same predictions, making the resulting
number optimistic — and *differentially* so, since a worse-calibrated model gains
more from fitting T on its own evaluation data. That number is the Gate 2
tiebreaker, so the bias could flip a winner. Temperature is now fitted per outer
fold on inner-OOF predictions from the training partition only, then applied to
that fold's test predictions.

## Consequences

- **Every recorded Gate 2 `ece_scaled` and `temperature` becomes non-comparable
  to history**, including the `gbt_tuned` ECE 0.047 that won it Gate 2. All four
  models are re-baselined together in one deliberate, documented run. Sequencing
  matters: reproduce the recorded numbers on unchanged code first to prove the
  environment, and only then apply this change.
- Gate 1 is unaffected — it gates on raw ECE and never applied a temperature.
- A gold slice would *not* have fixed this. Label circularity and this fitting
  bug are independent defects; only the first needs better labels.
- The per-fold temperatures and their spread are reported. Wide spread means a
  single shipped temperature is poorly estimated.
- The shipped artifact's `temperature` field was previously ignored by
  `MatcherModel`. It is now applied at inference — done while the value is still
  1.0 and the change is provably inert.

## Observed on the re-baseline (DEV-91, 2026-07-28)

Two things the decision above got slightly wrong in its reasoning, neither of which
changes the decision:

- **"Optimistic" is right about the mechanism and wrong as a prediction.** The
  guarantee is family-relative: a pooled temperature is the argmin of NLL on its
  own pool *among constant temperatures*, which is what makes the old number a
  fitted minimum rather than a measurement. But cross-fitting does not stay inside
  that family — it applies five per-fold constants, which can absorb fold-specific
  miscalibration a single global constant cannot. That second effect can outweigh
  the removal of the leak, and on this data it does: cross-fitted ECE is *lower*
  for three of four models, and cross-fitted NLL is lower for `logistic_tuned`.
  So the defensible claim is only that the reported number was never a held-out
  estimate — not that it flattered. The tiebreak should use the honest number
  regardless of which direction honesty moves it.
- **The per-fold spread turned out to matter most for the model that ships.**
  `logistic_tuned`, the deployable selection, produced per-fold temperatures of
  1.40, 1.40, 1.30, 0.50, 0.85 — folds disagreeing about whether to soften or
  sharpen at all, and no fold choosing the pooled Phase-3 reference.
  Its pooled Phase-3 temperature is 1.00, but that value does not transfer to the
  fixed-configuration artifact: export selects `C=1.0`, refits temperature on OOF
  predictions from that exact C, and reproduces 1.05. Served probabilities
  therefore soften slightly.
