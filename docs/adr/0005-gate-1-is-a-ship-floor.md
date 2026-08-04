---
status: accepted
---

# Gate 1 is a ship floor, split into a hard half and a mitigable half

Because shipping a neural matcher is a project requirement
([0004](./0004-neural-matcher-is-a-project-requirement.md)), kill criteria are
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

## Observed on flip readiness (DEV-99, 2026-08-03)

The decision is unchanged. **The mitigation it defines has never been implemented**, which
was not visible while no model needed it:

- "May still ship as the *ranking* source, with displayed percentages falling back to the
  formula's" is carried by `matcher_nn_v1.json` as `deployment.status: "ranking_only"` and
  `deployment.match_percent: "FALL BACK TO THE FORMULA"`, and by a caveat that does reach
  the response. **No serving code reads any of it.** The `Matcher` protocol
  (`services/matching/app/services/matcher.py`) has no `deployment` member, so both
  implementations discard the block at load, and `matching_service.py:323` sets
  `matchPercent` from the model's probability unconditionally.
- Consequence: flipping `MATCHER_MODEL_PATH` to a `ranking_only` artifact today would
  display exactly the uncalibrated percentages this ADR's mitigation exists to prevent.
  The mitigable half is therefore currently **undermitigated**, not mitigated.
- The fix is not a branch on one line. The formula's percentage is computed inside
  `_match_formula`, which does not run when the model scores, and that function returns
  only its own `TOP_N` — so a career the model ranked and the formula did not has no
  formula percentage computed anywhere. It also raises a question this ADR does not
  answer: substituted percentages are **not monotonic** in the model's ranking, so the UI
  would show a lower percentage above a higher one. Sizing, options and the two
  `xfail(strict=True)` tests pinning the gap:
  [`docs/dev-23-flip-readiness.md`](../dev-23-flip-readiness.md).
- **Nothing was changed in response.** Choosing between implementing this mitigation as
  written and amending it is reserved for the human who decides the flip (DEV-99).

## Amended: the mitigation is built, and it orders by the displayed number (2026-08-04)

The gap recorded above is closed. The mitigation now exists in code, **with one
deliberate change to what this ADR asked for**, decided by the human who owns the flip.

**As written, this ADR made the model "the ranking source" and the formula the source of
the number only.** That combination is what produces a non-monotonic display: the model
ranks A > B > C while the formula may score B above A, so `Results.jsx` — which animates
a bar per rank — would print *"1. A 55%, 2. B 71%"*.

**Amendment: within the model's selected set, the displayed order follows the displayed
percentage.** The top row therefore always carries the highest number. The consequence,
stated plainly because it narrows this ADR's claim: for a `ranking_only` artifact the
model contributes the **selection** of which careers appear, *not* their order. It is no
longer the ranking source; it is the shortlisting source, and the formula ranks within
that shortlist.

Rejected alternatives, and why:

- **Accept the non-monotonic display.** Honest per-career numbers, but it prints a lower
  percentage above a higher one in two places (`Results.jsx:96`, `History.jsx:187`).
  Rejected as a user-facing defect.
- **Keep the model's order and reassign the formula's percentages sorted descending.**
  Monotonic, but a career would display a number computed for a different career.
  Rejected explicitly: those numbers belong to nobody.
- **Clamp each percentage to the one above it.** Monotonic and every number stays
  attached to its own career, but percentages below the first are silently reduced, so
  the displayed number stops being the formula's. Rejected as a quieter untruth.

What ships as a result, for a `ranking_only` artifact: `matchPercent`, `score` and
`score_breakdown` are all the formula's, ordered by that percentage; `reasons` remain
model-derived, because why a career was *selected* is the judgement the model is still
trusted to make; and the model's own probability is preserved as
`score_breakdown.model_probability` so the selection stays auditable from the response
and from persisted history.

Unrestricted artifacts are unaffected. `matcher_logistic_v2.json` declares no
`deployment` block, so it keeps displaying its own probabilities exactly as before —
pinned by `test_an_unrestricted_artifact_still_displays_its_own_probability`, because a
default of "restricted" would have silently changed the incumbent's output. An
unrecognised `deployment.status` is a **load failure**, not a permissive default: a typo
must not hand an uncalibrated model permission to display its own numbers.

This changes no gate, no threshold and no recorded measurement. `MATCHER_MODEL_PATH`
remains blank — **the flip itself is still DEV-99's and still needs its own approval.**
What changes is that approving it no longer means shipping the uncalibrated percentages
this ADR's mitigation exists to prevent.
