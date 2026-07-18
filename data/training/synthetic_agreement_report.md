# Synthetic Agreement Report — LLM Panel Silver Labels

> **These are SILVER labels produced by a local LLM panel, not human expert ground
> truth.** All agreement numbers below measure consistency between LLM personas
> sharing one base model (qwen2.5:7b-instruct); they are NOT a human inter-expert noise
> ceiling and must never be presented as expert validation.

Generated: 2026-07-18T15:42:03Z  |  model: `qwen2.5:7b-instruct`  |  prompt: `panel-v2.0.0`  |  temperatures: hiring_manager=0.2, career_counselor=0.6, bootcamp_instructor=0.9

## Pool

- Profiles labeled (complete 3-persona panels): **241** (7 real from public.submissions, 234 synthetic-generated)
- Incomplete panels dropped: 0
- Failed votes (after retries): 0
- **NOTE:** public.submissions held only 7 real submissions at labeling time, so the
  pool is dominated by generated synthetic profiles (seeded/mixed/random over the
  answer space, adaptive branching respected). `profile_source` distinguishes them.

## Consensus filtering (>= 2/3 personas agree on top-1)

- High-consensus -> `silver_labels.parquet`: **235** (unanimous: 204)
- Low-agreement -> `ambiguous_labels.parquet`: **6**

## Synthetic agreement (NOT human agreement)

- Fleiss' kappa (3 personas, 16 careers): **0.879**
- Cohen's kappa hiring_manager vs career_counselor: 0.900
- Cohen's kappa hiring_manager vs bootcamp_instructor: 0.878
- Cohen's kappa career_counselor vs bootcamp_instructor: 0.861

Interpretation caution: personas share one base model, so high kappa here means
self-consistency, not correctness. Near-perfect kappa would be a red flag for
persona non-independence rather than a quality guarantee.

## Label distribution (silver consensus top-1)

| career | count | share |
|---|---|---|
| frontend | 37 | 15.7% |
| backend | 21 | 8.9% |
| data-science | 11 | 4.7% |
| devops | 20 | 8.5% |
| product-manager | 8 | 3.4% |
| ux-designer | 15 | 6.4% |
| fullstack | 14 | 6.0% |
| mobile | 8 | 3.4% |
| data-analyst | 19 | 8.1% |
| machine-learning | 7 | 3.0% |
| ai-engineer | 5 | 2.1% |
| cyber-security | 8 | 3.4% |
| qa-engineer | 25 | 10.6% |
| game-dev | 2 | 0.9% |
| technical-writer | 11 | 4.7% |
| software-architect | 24 | 10.2% |

## Per-persona top-1 distribution (all complete panels)

### hiring_manager
| career | count | share |
|---|---|---|
| frontend | 44 | 18.3% |
| backend | 21 | 8.7% |
| data-science | 11 | 4.6% |
| devops | 20 | 8.3% |
| product-manager | 9 | 3.7% |
| ux-designer | 16 | 6.6% |
| fullstack | 13 | 5.4% |
| mobile | 8 | 3.3% |
| data-analyst | 19 | 7.9% |
| machine-learning | 7 | 2.9% |
| ai-engineer | 5 | 2.1% |
| cyber-security | 8 | 3.3% |
| qa-engineer | 25 | 10.4% |
| game-dev | 1 | 0.4% |
| technical-writer | 10 | 4.1% |
| software-architect | 24 | 10.0% |
### career_counselor
| career | count | share |
|---|---|---|
| frontend | 34 | 14.1% |
| backend | 21 | 8.7% |
| data-science | 11 | 4.6% |
| devops | 21 | 8.7% |
| product-manager | 8 | 3.3% |
| ux-designer | 22 | 9.1% |
| fullstack | 15 | 6.2% |
| mobile | 9 | 3.7% |
| data-analyst | 18 | 7.5% |
| machine-learning | 7 | 2.9% |
| ai-engineer | 4 | 1.7% |
| cyber-security | 8 | 3.3% |
| qa-engineer | 25 | 10.4% |
| game-dev | 2 | 0.8% |
| technical-writer | 11 | 4.6% |
| software-architect | 25 | 10.4% |
### bootcamp_instructor
| career | count | share |
|---|---|---|
| frontend | 30 | 12.4% |
| backend | 21 | 8.7% |
| data-science | 11 | 4.6% |
| devops | 21 | 8.7% |
| product-manager | 8 | 3.3% |
| ux-designer | 14 | 5.8% |
| fullstack | 14 | 5.8% |
| mobile | 7 | 2.9% |
| data-analyst | 19 | 7.9% |
| machine-learning | 7 | 2.9% |
| ai-engineer | 5 | 2.1% |
| cyber-security | 8 | 3.3% |
| qa-engineer | 25 | 10.4% |
| game-dev | 18 | 7.5% |
| technical-writer | 10 | 4.1% |
| software-architect | 23 | 9.5% |

## Formula-vs-panel agreement (circularity check)

The current hand-authored questionnaire_fit heuristic's top-1 agrees with the panel
consensus on **40.9%** of silver profiles. High agreement means the
learned-vs-formula comparison in Phase 2 is partly circular (the panel may reason
like the hand weights); note this when reading Gate 1 results.

## Confidence

- Mean panel confidence (silver): 0.81
- Mean panel confidence (ambiguous): 0.80

## Gate 0 checklist

- [ ] Synthetic agreement acceptable (kappa neither near 0 nor suspiciously ~1.0) — see numbers above
- [ ] Label distribution plausible (no career ~0%, none dominating) — see table above
- [ ] Manual sanity check of the sample below passed

## Manual sanity-check sample (20 silver rows)

- **syn_0062** (synthetic) -> software-architect (votes 3/3, conf 0.80); answers `{"q1": 0, "q2": 1, "q3": 2, "q4": 1, "q5": 0, "q6": 0, "q7": 1, "q8": 1, "q9": 1, "q10": 1, "q11": 1, "q12": 0, "q13": 0, "q15": 1, "q18": 3}`; first explanation: "The individual chose 'drawing the big blueprint that everyone else builds on' for the tie-breaker question, which aligns with the role of a Software Architect who designs systems that survive scale and time. Additionally, their preference for 'tidying up the inside so it's easy to build on later' further supports the role of a Backend Engineer, as this involves ensuring the infrastructure is robus"
- **syn_t000_game-dev** (synthetic) -> frontend (votes 2/3, conf 0.80); answers `{"q1": 3, "q2": 0, "q4": 0, "q5": 1, "q6": 1, "q7": 1, "q8": 1, "q9": 3, "q10": 0, "q11": 0, "q12": 2, "q13": 1, "q14": 2, "q18": 2}`; first explanation: "The candidate chose to build a small video game with characters and levels for their tie-breaker question, which directly points towards the 'game-dev' career. Additionally, they preferred making it look and feel perfect as their finishing touch, further supporting their interest in visual design and polish, which aligns well with the role of a game developer."
- **syn_0173** (synthetic) -> qa-engineer (votes 3/3, conf 0.77); answers `{"q1": 1, "q2": 1, "q3": 0, "q4": 2, "q5": 1, "q6": 0, "q7": 3, "q8": 3, "q9": 3, "q10": 1, "q11": 3, "q12": 1, "q13": 3, "q15": 2, "q18": 3}`; first explanation: "The individual chose 'trying to break the app on purpose to find problems before users do' in the first tie-breaker question, which points to QA Engineer. In the second tie-breaker, they chose 'tidying up the inside so it's easy to build on later,' which points to both Backend and Software Architect roles. However, since they showed a strong preference for working behind the scenes with infrastruc"
- **syn_0002** (synthetic) -> data-science (votes 3/3, conf 0.83); answers `{"q1": 2, "q2": 2, "q3": 1, "q4": 3, "q5": 3, "q6": 3, "q7": 2, "q8": 2, "q10": null, "q11": 0, "q12": 3, "q13": 1, "q16": 1, "q18": 1}`; first explanation: "The individual's chosen tie-breaker option 'digging into messy numbers to figure out why something happened' strongly aligns with the role of a Data Scientist, making top1 'data-science'. The second-best fit is 'machine-learning', as both involve working with data but focus more on model training for predictions in the former and building AI products in the latter."
- **syn_0120** (synthetic) -> technical-writer (votes 2/3, conf 0.80); answers `{"q1": 0, "q2": 0, "q4": null, "q5": 1, "q6": 0, "q7": 2, "q8": 0, "q9": 0, "q10": 0, "q11": 2, "q12": 2, "q13": 1, "q14": 3, "q18": 0}`; first explanation: "The candidate chose to 'write drawings of how an app should look — someone else can build it' for the tie-breaker, which points towards technical writing as they are comfortable with documenting and explaining complex technology without directly coding or designing interfaces themselves. Additionally, their preference for showing off 'the clever machinery nobody sees that makes it work' also align"
- **syn_0102** (synthetic) -> fullstack (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 1, "q3": 1, "q4": 2, "q5": 1, "q6": 2, "q7": 1, "q8": 1, "q9": 2, "q10": 1, "q11": 2, "q12": 2, "q13": 1, "q15": 0, "q18": 3}`; first explanation: "The individual chose 'building whole features end to end, from the screen to the data behind it' for the first tie-breaker question, which strongly indicates a preference for Full-Stack Development. Additionally, their choice of tidying up the inside so it's easy to build on later in the second tie-breaker further supports the role of Backend Engineer, as this is more aligned with the responsibili"
- **syn_0189** (synthetic) -> cyber-security (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 3, "q4": 3, "q5": 0, "q6": 3, "q7": 0, "q8": 3, "q10": 0, "q11": 0, "q12": 1, "q13": null, "q17": 1, "q18": 3}`; first explanation: "The person chose 'checking whether someone broke in, and locking the doors better' for both tie-breaker questions, which strongly points towards a career focused on security. While they also showed interest in maintaining systems reliability (as indicated by their desire to 'tidy up the inside so it's easy to build on later'), the emphasis on defending against attacks aligns more closely with cybe"
- **syn_0086** (synthetic) -> technical-writer (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 1, "q3": null, "q4": 3, "q5": 3, "q6": 1, "q7": 3, "q8": 1, "q9": 3, "q10": 3, "q11": 3, "q12": 2, "q13": 3, "q15": null, "q18": 0}`; first explanation: 'The candidate chose to write a simple guide as the finishing touch they would most enjoy, which points strongly towards the role of Technical Writer. Additionally, their preference for keeping systems running without downtime and their comfort with technical detail align well with backend engineering, making these the top two choices.'
- **syn_t020_game-dev** (synthetic) -> frontend (votes 2/3, conf 0.82); answers `{"q1": 3, "q2": 0, "q4": 0, "q5": 1, "q6": 1, "q7": 1, "q8": 1, "q9": 3, "q10": 0, "q11": 0, "q12": 2, "q13": 0, "q14": 2, "q18": 2}`; first explanation: "The candidate chose 'a small video game with characters and levels' for the tie-breaker question, indicating a strong preference for creating interactive experiences, which aligns closely with being a Game Developer. Additionally, they enjoyed making it look and feel perfect, suggesting a focus on visual aesthetics, which is also a key aspect of Game Development. While Frontend Development shares "
- **syn_0008** (synthetic) -> data-analyst (votes 3/3, conf 0.87); answers `{"q1": 1, "q2": 2, "q3": 3, "q4": 2, "q5": 2, "q6": 2, "q7": 3, "q8": 2, "q10": 2, "q11": 2, "q12": 3, "q13": 2, "q16": 0, "q18": 0}`; first explanation: "The candidate chose 'making clear charts and reports that show what happened,' which directly points to data analyst. Additionally, their preference for writing a simple guide when finished something they are proud of further supports the role of a technical writer, but given the strong tie-breaker choice, data analyst is the stronger fit."
- **syn_t022_game-dev** (synthetic) -> frontend (votes 3/3, conf 0.80); answers `{"q1": null, "q2": 0, "q4": 0, "q5": 2, "q6": 1, "q7": 1, "q8": 0, "q9": 3, "q10": 0, "q11": 0, "q12": 1, "q13": 1, "q14": null, "q18": 2}`; first explanation: "The candidate's preference for making things look beautiful and feeling that success means users loving the product they helped build strongly aligns with frontend development, where crafting an aesthetically pleasing interface is a key focus. Additionally, their choice of 'making it look and feel perfect' as the finishing touch most fun indicates a strong desire to enhance the visual and user exp"
- **syn_0048** (synthetic) -> frontend (votes 3/3, conf 0.83); answers `{"q1": null, "q2": 0, "q4": 0, "q5": 1, "q6": null, "q7": 1, "q8": 1, "q9": 1, "q10": 0, "q11": 0, "q12": 2, "q13": 1, "q14": 0, "q18": 2}`; first explanation: 'The candidate chose to make a website in their free time, indicating a preference for building interactive interfaces. They also indicated that they enjoy making things look and feel perfect, which aligns closely with the role of a frontend developer who focuses on user interface and experience. While UX design also involves this aspect, the frontend role is more directly about crafting web interf'
- **syn_t025_game-dev** (synthetic) -> frontend (votes 3/3, conf 0.83); answers `{"q1": 0, "q2": 0, "q4": 0, "q5": 1, "q6": 1, "q7": 1, "q8": 1, "q9": 3, "q10": 0, "q11": 0, "q12": 2, "q13": 1, "q14": 0, "q18": 2}`; first explanation: 'The person chose to build a website in their free time and enjoys making it look and feel perfect, which aligns most with the frontend developer role of crafting interactive, accessible web interfaces that delight users. The UX Designer role also fits well due to their interest in visual design, but they showed a stronger inclination towards coding and technical implementation.'
- **syn_0023** (synthetic) -> mobile (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 0, "q4": null, "q5": 1, "q6": 2, "q7": 3, "q8": 3, "q9": 2, "q10": 0, "q11": 0, "q12": 2, "q13": 0, "q14": 1, "q18": 2}`; first explanation: "The candidate's choice of 'an app for phones that people carry everywhere' in the tie-breaker question points strongly towards Mobile Developer, as it aligns with their interest in building applications for smartphones. Their preference to focus on making things look and feel perfect further supports this choice, as user interface and experience are key aspects of mobile app development. While Fro"
- **syn_0194** (synthetic) -> mobile (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 0, "q4": 2, "q5": 2, "q6": 1, "q7": 2, "q8": 2, "q9": 2, "q10": 3, "q11": 1, "q12": 1, "q13": 1, "q14": 1, "q18": null}`; first explanation: "The person chose to build an app for phones that people carry everywhere in the tie-breaker question, which points most strongly to a 'mobile' developer. Additionally, they expressed a preference for making things look beautiful and visual, which aligns with both frontend and mobile development roles. However, since their description of enjoying the underlying machinery over visuals slightly leans"
- **syn_0140** (synthetic) -> qa-engineer (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 1, "q3": 3, "q4": 0, "q5": 2, "q6": 1, "q7": 0, "q8": 3, "q9": 2, "q10": 1, "q11": 3, "q12": 3, "q13": 3, "q15": 2, "q18": 1}`; first explanation: "The person chose 'trying to break the app on purpose to find problems before users do' for their tie-breaker question, which directly points to QA Engineer. Additionally, they showed a preference for analyzing results and reporting findings when things go sideways, indicating a focus on reliability and infrastructure, which aligns well with the role of a Backend Engineer."
- **syn_0012** (synthetic) -> qa-engineer (votes 3/3, conf 0.83); answers `{"q1": 2, "q2": 3, "q4": 0, "q5": 1, "q6": 1, "q7": 2, "q8": 1, "q10": 2, "q11": 1, "q12": 1, "q13": 3, "q17": 3, "q18": 0}`; first explanation: "The candidate chose 'writing the checks that would have caught the problem before launch' in the tie-breaker question, which points to QA Engineer. Additionally, they indicated a preference for showing off the stability of their project ('that it ran for months without breaking once'), further aligning with QA Engineering's focus on ensuring reliability and robustness."
- **syn_0105** (synthetic) -> software-architect (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 1, "q3": 2, "q4": 3, "q5": 1, "q6": 3, "q7": 1, "q8": 1, "q9": 0, "q10": 1, "q11": 0, "q12": 0, "q13": 1, "q15": 1, "q18": 0}`; first explanation: "The candidate chose 'drawing the big blueprint that everyone else builds on' for the tie-breaker question, which points to 'software-architect'. Additionally, their preference for writing a simple guide aligns more with technical documentation work typically done by software architects when setting up frameworks and systems. While they also showed interest in backend roles, the overall profile ind"
- **syn_t023_game-dev** (synthetic) -> frontend (votes 3/3, conf 0.80); answers `{"q1": null, "q2": null, "q4": 0, "q5": 1, "q6": 1, "q7": 1, "q8": 2, "q10": 0, "q11": 0, "q12": 2, "q13": 1, "q18": 2}`; first explanation: 'The candidate values a polished end product and enjoys deep coding, which aligns well with frontend development. They also show interest in APIs and React, suggesting potential full-stack capabilities.'
- **syn_0017** (synthetic) -> backend (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 1, "q3": 2, "q4": null, "q5": 3, "q6": 1, "q7": 1, "q8": 1, "q9": 1, "q10": 1, "q11": 1, "q12": 0, "q13": 2, "q15": 3, "q18": 3}`; first explanation: "The candidate chose 'building the hidden engine that quietly makes everything work' in the first tie-breaker, which directly points to Backend Engineer. In the second tie-breaker, they chose 'tidying up the inside so it's easy to build on later,' which aligns with Software Architect. However, their preference for working heads-down and focusing on solving logical puzzles leans more towards Backend"
