---
status: accepted
---

# Gate 1 is a ship floor, split into a hard half and a mitigable half

Because shipping a neural matcher is a project requirement
([0001](./0001-neural-matcher-is-a-project-requirement.md)), kill criteria are
meaningless — there is no outcome in which we walk away. Gate 1 therefore stops
being an admission test in a contest and becomes the floor a model must meet to
serve at all. Its two halves are not equally negotiable, so they are treated
differently.

- **Top-2 stability >= 0.60 is a hard floor with no mitigation.** An unstable
  model gives different recommendations to the same user depending on which
  resample trained it. The ranking is the product; there is nothing to degrade
  into. Failing this escalates as a project-level finding — "this dataset cannot
  support a stable 16-class neural matcher at n=232" — rather than shipping.
- **ECE <= 0.10 is a floor with a defined mitigation.** It matters because
  `Results.jsx` renders `matchPercent`. A model that fails it may still ship as
  the *ranking* source, with displayed percentages falling back to the formula's.

## Consequences

- This bar is stricter than the incumbent production path has ever met: the
  formula's ECE is computed on softmax-normalised pseudo-probabilities and is
  flagged "directional only". We apply it anyway, because it is the standard the
  repo already applies to every learned model.
- It is known achievable on this data — `logistic_tuned` clears both
  (ECE 0.0341, stability 0.6375).
