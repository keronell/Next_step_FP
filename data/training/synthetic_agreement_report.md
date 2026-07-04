# Synthetic Agreement Report — LLM Panel Silver Labels

> **These are SILVER labels produced by a local LLM panel, not human expert ground
> truth.** All agreement numbers below measure consistency between LLM personas
> sharing one base model (qwen2.5:7b-instruct); they are NOT a human inter-expert noise
> ceiling and must never be presented as expert validation.

Generated: 2026-07-04T08:10:26Z  |  model: `qwen2.5:7b-instruct`  |  prompt: `panel-v1.1.0`  |  temperatures: hiring_manager=0.2, career_counselor=0.6, bootcamp_instructor=0.9

## Pool

- Profiles labeled (complete 3-persona panels): **207** (7 real from public.submissions, 200 synthetic-generated)
- Incomplete panels dropped: 0
- Failed votes (after retries): 0
- **NOTE:** public.submissions held only 7 real submissions at labeling time, so the
  pool is dominated by generated synthetic profiles (seeded/mixed/random over the
  answer space, adaptive branching respected). `profile_source` distinguishes them.

## Consensus filtering (>= 2/3 personas agree on top-1)

- High-consensus -> `silver_labels.parquet`: **205** (unanimous: 174)
- Low-agreement -> `ambiguous_labels.parquet`: **2**

## Synthetic agreement (NOT human agreement)

- Fleiss' kappa (3 personas, 6 careers): **0.864**
- Cohen's kappa hiring_manager vs career_counselor: 0.892
- Cohen's kappa hiring_manager vs bootcamp_instructor: 0.850
- Cohen's kappa career_counselor vs bootcamp_instructor: 0.850

Interpretation caution: personas share one base model, so high kappa here means
self-consistency, not correctness. Near-perfect kappa would be a red flag for
persona non-independence rather than a quality guarantee.

## Label distribution (silver consensus top-1)

| career | count | share |
|---|---|---|
| frontend | 17 | 8.3% |
| backend | 50 | 24.4% |
| data-science | 50 | 24.4% |
| devops | 38 | 18.5% |
| product-manager | 14 | 6.8% |
| ux-designer | 36 | 17.6% |

## Per-persona top-1 distribution (all complete panels)

### hiring_manager
| career | count | share |
|---|---|---|
| frontend | 15 | 7.2% |
| backend | 49 | 23.7% |
| data-science | 50 | 24.2% |
| devops | 37 | 17.9% |
| product-manager | 16 | 7.7% |
| ux-designer | 40 | 19.3% |
### career_counselor
| career | count | share |
|---|---|---|
| frontend | 18 | 8.7% |
| backend | 50 | 24.2% |
| data-science | 50 | 24.2% |
| devops | 38 | 18.4% |
| product-manager | 16 | 7.7% |
| ux-designer | 35 | 16.9% |
### bootcamp_instructor
| career | count | share |
|---|---|---|
| frontend | 18 | 8.7% |
| backend | 54 | 26.1% |
| data-science | 51 | 24.6% |
| devops | 39 | 18.8% |
| product-manager | 12 | 5.8% |
| ux-designer | 33 | 15.9% |

## Formula-vs-panel agreement (circularity check)

The current hand-authored questionnaire_fit heuristic's top-1 agrees with the panel
consensus on **43.4%** of silver profiles. High agreement means the
learned-vs-formula comparison in Phase 2 is partly circular (the panel may reason
like the hand weights); note this when reading Gate 1 results.

## Confidence

- Mean panel confidence (silver): 0.80
- Mean panel confidence (ambiguous): 0.80

## Gate 0 checklist — PASSED (prototype-grade) at panel-v1.1.0

- [x] Synthetic agreement acceptable: Fleiss kappa 0.864 (down from 0.930 at v1.0.1
      after per-persona temperatures 0.2/0.6/0.9). Still high because all personas
      share one base model — recorded as a limitation, not treated as quality proof.
- [x] Label distribution plausible: all 6 careers populated (7–24% each). At v1.0.1
      ux-designer had 0 labels and product-manager 2.9%; the v1.1.0 neutrality
      instruction fixed the developer-role default.
- [x] Manual sanity check passed on a spot-check of 8+20 rows: explanations cite the
      actual answers; design/PM-leaning profiles now route to ux-designer /
      product-manager. Residual quirks: confidence is nearly constant (~0.8, weakly
      informative) and occasional secondary-explanation stretches.

### Version history

- `panel-v1.0.1` (archived logs: `panel_votes_v1.0.1.jsonl`): single temperature 0.2.
  FAILED Gate 0 — kappa 0.930 (clone effect), ux-designer 0%, product-manager 2.9%,
  formula agreement 34.5%.
- `panel-v1.1.0` (current): per-persona temperatures + equal-validity instruction for
  non-coding careers. Kappa 0.864, all classes populated, formula agreement 43.4%.

## Manual sanity-check sample (20 silver rows)

- **syn_0008** (synthetic) -> data-science (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 2, "q3": 0, "q4": null, "q5": 2, "q6": 3, "q7": 2, "q8": 2, "q10": 2}`; first explanation: "The candidate's interest in wrangling data and finding patterns, coupled with a focus on business impact, strongly aligns with the role of a Data Scientist."
- **syn_0002** (synthetic) -> devops (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 3, "q4": 2, "q5": 2, "q6": 2, "q7": 2, "q8": 2, "q10": 2}`; first explanation: 'The candidate’s comfort with code, interest in complex system maintenance, and focus on data-driven insights align well with DevOps. They also show traits of a Product Manager, such as analyzing results and driving business impact.'
- **syn_0093** (synthetic) -> backend (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 1, "q3": 3, "q4": 1, "q5": 1, "q6": 0, "q7": 3, "q8": 3, "q9": 1, "q10": 0}`; first explanation: 'The person enjoys solving logical puzzles and prefers writing code, which aligns well with backend engineering. They also show interest in data by feeling curious about datasets.'
- **syn_0126** (synthetic) -> ux-designer (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 0, "q4": 3, "q5": null, "q6": 2, "q7": 3, "q8": 1, "q9": 3, "q10": 3}`; first explanation: "The person values visual design highly and finds it their 'happy place,' indicating a strong fit for UX Designer. Their preference for analysis and discussion also aligns with the collaborative nature of this role."
- **syn_0061** (synthetic) -> frontend (votes 3/3, conf 0.77); answers `{"q1": 1, "q2": 1, "q3": 0, "q4": 1, "q5": 1, "q6": null, "q7": 1, "q8": 0, "q9": 3, "q10": 0}`; first explanation: 'The person prefers elegant code and finds visual design appealing, aligning well with frontend development. They also enjoy solving logical puzzles.'
- **syn_0088** (synthetic) -> ux-designer (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 0, "q4": 0, "q5": 1, "q6": 0, "q7": 0, "q8": 1, "q9": 3, "q10": 0}`; first explanation: "The candidate's preference for visual design, making things look beautiful and valuing a polished final product aligns strongly with UX Designer. Additionally, they naturally drift toward writing code in teams, which fits better with the frontend role."
- **syn_0154** (synthetic) -> data-science (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 2, "q3": 3, "q4": 3, "q5": 1, "q6": 0, "q7": 0, "q8": 1, "q10": 2}`; first explanation: "The person's interest in wrangling data and finding patterns, as well as their desire for insights with business impact, aligns closely with a Data Scientist role."
- **syn_0157** (synthetic) -> product-manager (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 1, "q3": 0, "q4": 0, "q5": 0, "q6": 1, "q7": 1, "q8": null, "q9": 1, "q10": 0}`; first explanation: 'The person prefers talking to users and shaping vision over coding, and values user satisfaction highly.'
- **syn_0141** (synthetic) -> devops (votes 3/3, conf 0.80); answers `{"q1": 0, "q2": 3, "q4": 3, "q5": 2, "q6": 2, "q7": 1, "q8": 0, "q10": 0}`; first explanation: 'The person values system reliability and excels in keeping complex systems running, aligning well with DevOps. They also show a preference for analysis and discussion, which can be key in both DevOps and backend roles.'
- **syn_0177** (synthetic) -> product-manager (votes 2/3, conf 0.80); answers `{"q1": 0, "q2": 1, "q3": null, "q4": 1, "q5": 2, "q6": 1, "q7": 2, "q8": 3, "q9": 3, "q10": 0}`; first explanation: "The person values deep focus on elegant code and solving logical puzzles, aligning well with product management's strategic vision. Additionally, their interest in team analysis and reporting findings suggests a natural fit for this role."
- **syn_0186** (synthetic) -> backend (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 0, "q4": 3, "q5": null, "q6": 3, "q7": 1, "q8": 0, "q9": 0, "q10": 3}`; first explanation: "The candidate's comfort with writing code and desire for a system that never goes down align well with backend engineering, while their preference for independently owning an end-to-end system also fits devops."
- **syn_0159** (synthetic) -> backend (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 3, "q4": 1, "q5": 3, "q6": 0, "q7": 0, "q8": 2, "q10": null}`; first explanation: "The candidate's comfort with writing code, desire for elegant solutions, and focus on complex systems align well with backend development. Their preference for building infrastructure also supports a strong fit in devops."
- **syn_0058** (synthetic) -> data-science (votes 3/3, conf 0.80); answers `{"q1": 0, "q2": 2, "q3": 2, "q4": 1, "q5": 3, "q6": 0, "q7": 0, "q8": 0, "q10": 0}`; first explanation: "The person's interest in wrangling data and finding patterns, along with their desire for elegant code, suggests a strong fit for data science. Their inclination towards building infrastructure aligns well with backend engineering."
- **syn_0170** (synthetic) -> devops (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 3, "q4": 0, "q5": 3, "q6": 0, "q7": 3, "q8": 2, "q10": 3}`; first explanation: "The candidate's interest in keeping complex systems running and a preference for infrastructure aligns strongly with devops, while their love for zero-downtime deploys further supports this choice."
- **syn_0066** (synthetic) -> devops (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 3, "q4": 3, "q5": 2, "q6": 2, "q7": 3, "q8": 2, "q10": 3}`; first explanation: "The candidate's interest in keeping complex systems running and their desire for zero-downtime deploys align well with DevOps roles. Their preference for a mix of analysis and discussion also fits well with the need to analyze results and report findings."
- **syn_0146** (synthetic) -> product-manager (votes 3/3, conf 0.80); answers `{"q1": 0, "q2": null, "q4": 2, "q5": 1, "q6": 3, "q7": 2, "q8": 2, "q10": 0}`; first explanation: 'The person values user satisfaction and prefers owning a system end-to-end, which aligns with product management. They also prefer working independently, which can fit into frontend development.'
- **syn_0011** (synthetic) -> ux-designer (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 0, "q4": 0, "q5": 3, "q6": 0, "q7": 0, "q8": 0, "q9": 1, "q10": 0}`; first explanation: 'The person values visual aesthetics and user experience highly, aligning with UX Designer, and desires a polished product that users love, which is a core aspect of this role.'
- **syn_0075** (synthetic) -> data-science (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 2, "q3": 2, "q4": 0, "q5": 3, "q6": 0, "q7": 1, "q8": 3, "q10": 3}`; first explanation: "The candidate's interest in wrangling data and a preference for infrastructure suggest they would thrive as a Data Scientist or Backend Engineer, with Data Science being slightly more aligned."
- **syn_0079** (synthetic) -> backend (votes 3/3, conf 0.82); answers `{"q1": 3, "q2": 2, "q3": 0, "q4": 1, "q5": 3, "q6": 2, "q7": 1, "q8": 2, "q10": 1}`; first explanation: "The candidate's comfort with writing code daily, preference for elegant solutions and working on infrastructure align well with backend engineering. The enjoyment in wrangling data also suggests a fit for data science."
- **syn_0137** (synthetic) -> backend (votes 3/3, conf 0.82); answers `{"q1": 3, "q2": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 2, "q10": 1}`; first explanation: "The person's comfort with writing code daily and a preference for keeping complex systems running align well with backend engineering."
