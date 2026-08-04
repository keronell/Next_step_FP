---
status: accepted
---

# The Residual Matcher's linear branch is frozen, not trained

The Residual Matcher computes `logits = frozen_logistic_logits + alpha * MLP(x)`,
where the logistic branch is fitted separately on the same partition the MLP
trains on and then held fixed, and `alpha` is a hyperparameter selected by inner
CV from `{0, 0.25, 0.5, 1.0}`. At n=232 with 84 features and 16 classes the
binding constraint is variance, not expressiveness: a jointly-trained network
would spend scarce capacity re-learning linear structure that is already
available in closed form.

## Considered options

An earlier revision proposed training both branches jointly, warm-started at the
logistic solution with split weight-decay groups, and claimed this made the model
"never worse than logistic". That claim was false. Initialisation constrains only
the starting predictions; training minimises soft-target cross-entropy while the
reported metric is top-2, and early stopping selects on validation loss, so the
network can and does finish below its own initialisation.

## Consequences

- Do not "fix" this by unfreezing the linear branch. Freezing is the point.
- With `alpha = 0` the model is *exactly* logistic regression. That is a genuine
  possible outcome, not a degenerate one — so it is pre-registered that `alpha=0`
  selected in >=3 of 5 outer folds is reported as "no non-linear signal found",
  and disqualifies the Residual Matcher from being the shipped neural model.
- Attribution splits cleanly: the frozen branch keeps exact linear attribution,
  and integrated gradients cover only `alpha * MLP`.
- There is no weight-decay parameter-group split to maintain, because the linear
  branch has no parameters to decay.

## Observed on implementation (DEV-92, 2026-07-29)

The decision is unchanged. One claim above needed a specific implementation to be
literally true rather than approximately true, which is worth recording because
the obvious alternative looks correct and is not:

- **"With `alpha = 0` the model is *exactly* logistic regression" holds only if the
  frozen branch contributes `decision_function` values.** For a multiclass problem
  sklearn's `LogisticRegression.predict_proba` *is* `softmax(decision_function(X))`,
  so summing decision values with `alpha * MLP` and applying sklearn's own softmax
  reproduces its output bit for bit. Taking `log(predict_proba)` as the base logits
  is the natural-looking alternative and is mathematically equivalent — softmax is
  shift-invariant — but the exponential round-trip loses the last bits: it passes
  `np.allclose` and fails `np.array_equal`. That is not asserted here but held as a
  property, by
  `test_residual_matcher.py::test_taking_log_probabilities_as_the_base_logits_would_lose_the_identity`,
  so this paragraph fails loudly rather than quietly ageing if the round-trip ever
  becomes exact. A retreat to the Incumbent that is only approximate is not the
  safeguard this ADR describes, so the exactness is asserted bit-identically and
  `predict_proba` carries no branch on `alpha` that could make that assertion
  circular.
- Nothing here is evidence about whether the residual helps. No `alpha` has been
  selected on the real data yet; the pre-registered >=3-of-5 rule is encoded in
  `train_models.alpha_zero_verdict` and read by the sweep.
