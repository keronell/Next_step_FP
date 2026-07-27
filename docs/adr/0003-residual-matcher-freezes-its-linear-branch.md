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
