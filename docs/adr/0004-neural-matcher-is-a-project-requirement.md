---
status: accepted
---

# The served matcher is a neural network because the project requires one

DEV-23 asks for a neural network as the production scoring path. Investigation
established that the NN loses to both `logistic_tuned` and `gbt_tuned` on every
metric currently measurable, and that all of those metrics are agreement with
silver labels that are ~94% circular with the hand-authored `careers.json` bonus
table — so none of them is evidence of real-world recommendation quality anyway.
Shipping a neural network is a hard deliverable requirement of the project, not a
conclusion drawn from the evidence. We ship it, and we say so.

## Consequences

- The NN is not claimed to be the best model. Reports state its standing against
  `logistic_tuned` and `gbt_tuned` in full, with paired confidence intervals, and
  name the requirement as the reason it serves.
- There are no kill criteria, because abandoning the NN is not an available
  outcome. What replaces them is a **ship floor** — see
  [0005](./0005-gate-1-is-a-ship-floor.md).
- The effect-size bar that would have gated displacement becomes a reporting
  standard: it sizes the gap rather than authorising the switch.
- Serving work (`matcher_nn.py`, export, integrated-gradients attribution) is
  core scope, not conditional on a contest outcome.
