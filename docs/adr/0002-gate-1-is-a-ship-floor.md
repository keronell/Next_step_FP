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

## Observed on the decision writeup (DEV-98, 2026-08-03)

The decision is unchanged. One attribution above is wrong and matters, because the
floor's achievability is the sentence the whole "we apply it anyway" argument rests on:

- **ECE 0.0341 / stability 0.6375 belong to `logistic`, not `logistic_tuned`.** They are
  `gate1_verdict.json`'s `logistic` row — the **fixed `C = 1.0`** configuration that
  `matcher_logistic_v2.json` actually serialises. Gate 2's `logistic_tuned` re-selects
  `C` per outer fold (4.0, 4.0, 4.0, 0.05, 0.25) and its *raw* ECE is **0.103**, which
  would fail this floor. Both numbers are honest; they describe different models.
- **The claim survives the correction, and is if anything stronger.** The floor is known
  achievable by the exact configuration that ships, rather than by a nested protocol
  with no artifact. `nn_rework.md`'s C-sensitivity table shows raw ECE ranging 0.0341 at
  `C = 1.0` to 0.2898 at `C = 0.05` for the identical estimator, so raw calibration here
  tracks `C` rather than model family — which is why naming the configuration, not the
  protocol, is what makes the sentence true.
- Consequence for `CONTEXT.md`'s **Incumbent**: it is the exported artifact, since
  `logistic_tuned` has no single configuration and therefore cannot be Deployable.
