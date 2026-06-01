# Neural Matcher — LLM Council Verdict

**Question:** Is the proposed workflow — synthetic LLM annotations as training targets for a small MLP (40→64→32→16), with job-ad RAG as auxiliary signal — a sound approach for matching questionnaire answers to career fields?

**Date:** 2026-05-31

---

## Where the Council Agrees

**The supervision signal is not grounded in reality.** Every advisor landed on the same structural problem from a different angle: the system learns to approximate what an LLM *believes* career fields look like, not what career fit actually is. The Contrarian called it circular validation. The First Principles Thinker called it a proxy of a proxy. The Outsider called it self-referential. The Executor accidentally confirmed it by proposing to measure accuracy against the same synthetic labels used for training — that's consistency checking, not measurement.

**The job posting corpus is the only empirically grounded component.** 1,575 job ads are artifacts of what labor markets actually require. That is the one thing in the pipeline that did not originate from an LLM's prior.

**The entropy-guided adaptive quiz is the highest-risk feature to ship early.** If the model is miscalibrated — and there is strong reason to believe it will be — the quiz will confidently terminate early and return a confidently wrong recommendation. High confidence is not a signal of correctness on a model never calibrated against ground truth.

---

## Where the Council Clashes

**Sequencing: ship fast vs. fix the foundation first.** The Executor says build the pipeline, get baseline numbers, iterate. The Contrarian, First Principles Thinker, and Outsider say you cannot iterate your way out of an invalid foundation. Baseline top-3 accuracy measured against synthetic labels only tells you how well the MLP learned the LLM's priors — not whether the recommendations are good. The Executor is not wrong that the system is buildable. The Executor is wrong that building it faster resolves the epistemic problem.

**LLM annotations: discard or demote?** The First Principles Thinker says invert the architecture entirely — make job embeddings primary, reduce LLM to regularization. The Executor implies LLM annotations are fine as a scaffold if balanced across personas. For an academic project, First Principles wins: *"we grounded field definitions in empirical labor market data"* survives a thesis committee. *"We asked an LLM to simulate career personas"* does not.

---

## Blind Spots the Council Caught

**The questionnaire instrument itself has never been validated.** This emerged convergently across 4 of 5 peer reviewers and no individual advisor caught it. The 1,611 questions mapped onto 40 trait dimensions have no demonstrated psychometric validity — no convergent validity, no test-retest reliability, no construct validity against career aptitude literature (Holland codes, O*NET interest profiles, Big Five career correlates). Self-report Likert items carry *systematic* biases — social desirability effects, reference group effects, response style variance — that corrupt the input distribution directionally. No downstream model architecture can recover from systematic input corruption.

**The 16-field taxonomy has no external anchor.** O*NET, ISCO-08, and SOC codes exist precisely to make occupational classification verifiable. An internally invented target space means the classification task is definitionally unverifiable — there is no check on whether the 16 fields are well-separated, jointly exhaustive, or meaningful to labor markets. Even a surface mapping of the 16 fields to O*NET clusters — a half-day task — transforms "invented taxonomy" into "taxonomy cross-referenced against the US labor market standard."

**User engagement is not a validity signal.** Treating real user sessions as labeled training data makes the circularity worse, not better. A user completing a session does not confirm the recommendation was correct.

---

## The Recommendation

**Build the system, but restructure the supervision hierarchy and add one validation anchor before any training runs.**

Make job-posting embeddings the **primary** supervision signal. C3 (predict field from job embedding) is not auxiliary — it should be the training core. LLM annotations function as label smoothing only, not as ground truth. This is a reweighting of the loss function and a reframing, not a large architectural change. This framing is academically defensible; the current one is not.

- Drop **C2** (RAG rerank) — market skew at 81% from two sources hurts more than it helps.
- Keep **C1** (late fusion with field prototype vectors) — low-cost and paper-defensible.
- Do **not** ship the entropy-guided adaptive quiz until the base model passes the persona separation test below.
- Map the 16-field taxonomy to O*NET occupation clusters before thesis submission — this is a half-day task that makes the target space externally verifiable.

---

## The One Thing to Do First

**Manually answer the full questionnaire three times** — once as a prototypical frontend developer, once as a data scientist, once as a UX designer — then run all three through the LLM annotation pipeline and compare the resulting soft-label distributions.

If the pipeline cannot clearly separate three profiles that any hiring manager would distinguish on sight, the annotation foundation is broken and must be fixed before anything else. Everything else — architecture choices, fusion strategy, quiz logic, training volume — is downstream of this test, and none of it matters if this test fails.

---

## Council Composition

| Advisor | Core point |
|---------|-----------|
| The Contrarian | Circular validation: MLP distills LLM priors, not career fit. No mechanism to detect confident miscalibration. |
| The First Principles Thinker | Wrong supervision hierarchy. Job embeddings are the only empirical signal; invert the architecture. |
| The Expansionist | Real user interactions are the real training data; build for it from day one. Job postings can explain recommendations, not just rank them. |
| The Outsider | Likert-4 collapse was patched not solved; flat LLM targets will produce flat model outputs. Taxonomy unexplained to any external observer. |
| The Executor | MLP architecture is fine; annotation pipeline inter-field variance is the single point of failure. Skip C2, ship C1. |

**Peer review unanimous verdict:** First Principles Thinker gave the strongest response. Executor had the biggest blind spot (treats execution velocity as an answer to an epistemic validity problem).
