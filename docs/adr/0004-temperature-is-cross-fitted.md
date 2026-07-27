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
