# Synthetic Agreement Report — LLM Panel Silver Labels

> **These are SILVER labels produced by a local LLM panel, not human expert ground
> truth.** All agreement numbers below measure consistency between LLM personas
> sharing one base model (qwen2.5:7b-instruct); they are NOT a human inter-expert noise
> ceiling and must never be presented as expert validation.

Generated: 2026-07-18T14:09:36Z  |  model: `qwen2.5:7b-instruct`  |  prompt: `panel-v2.0.0`  |  temperatures: hiring_manager=0.2, career_counselor=0.6, bootcamp_instructor=0.9

## Pool

- Profiles labeled (complete 3-persona panels): **207** (7 real from public.submissions, 200 synthetic-generated)
- Incomplete panels dropped: 0
- Failed votes (after retries): 0
- **NOTE:** public.submissions held only 7 real submissions at labeling time, so the
  pool is dominated by generated synthetic profiles (seeded/mixed/random over the
  answer space, adaptive branching respected). `profile_source` distinguishes them.

## Consensus filtering (>= 2/3 personas agree on top-1)

- High-consensus -> `silver_labels.parquet`: **207** (unanimous: 185)
- Low-agreement -> `ambiguous_labels.parquet`: **0**

## Synthetic agreement (NOT human agreement)

- Fleiss' kappa (3 personas, 16 careers): **0.923**
- Cohen's kappa hiring_manager vs career_counselor: 0.916
- Cohen's kappa hiring_manager vs bootcamp_instructor: 0.937
- Cohen's kappa career_counselor vs bootcamp_instructor: 0.916

Interpretation caution: personas share one base model, so high kappa here means
self-consistency, not correctness. Near-perfect kappa would be a red flag for
persona non-independence rather than a quality guarantee.

## Label distribution (silver consensus top-1)

| career | count | share |
|---|---|---|
| frontend | 23 | 11.1% |
| backend | 21 | 10.1% |
| data-science | 11 | 5.3% |
| devops | 20 | 9.7% |
| product-manager | 3 | 1.4% |
| ux-designer | 13 | 6.3% |
| fullstack | 12 | 5.8% |
| mobile | 7 | 3.4% |
| data-analyst | 17 | 8.2% |
| machine-learning | 7 | 3.4% |
| ai-engineer | 5 | 2.4% |
| cyber-security | 8 | 3.9% |
| qa-engineer | 25 | 12.1% |
| game-dev | 1 | 0.5% |
| technical-writer | 11 | 5.3% |
| software-architect | 23 | 11.1% |

## Per-persona top-1 distribution (all complete panels)

### hiring_manager
| career | count | share |
|---|---|---|
| frontend | 24 | 11.6% |
| backend | 21 | 10.1% |
| data-science | 11 | 5.3% |
| devops | 20 | 9.7% |
| product-manager | 4 | 1.9% |
| ux-designer | 14 | 6.8% |
| fullstack | 11 | 5.3% |
| mobile | 7 | 3.4% |
| data-analyst | 17 | 8.2% |
| machine-learning | 7 | 3.4% |
| ai-engineer | 5 | 2.4% |
| cyber-security | 8 | 3.9% |
| qa-engineer | 25 | 12.1% |
| game-dev | 0 | 0.0% |
| technical-writer | 10 | 4.8% |
| software-architect | 23 | 11.1% |
### career_counselor
| career | count | share |
|---|---|---|
| frontend | 20 | 9.7% |
| backend | 21 | 10.1% |
| data-science | 11 | 5.3% |
| devops | 21 | 10.1% |
| product-manager | 3 | 1.4% |
| ux-designer | 14 | 6.8% |
| fullstack | 13 | 6.3% |
| mobile | 8 | 3.9% |
| data-analyst | 16 | 7.7% |
| machine-learning | 7 | 3.4% |
| ai-engineer | 4 | 1.9% |
| cyber-security | 8 | 3.9% |
| qa-engineer | 25 | 12.1% |
| game-dev | 1 | 0.5% |
| technical-writer | 11 | 5.3% |
| software-architect | 24 | 11.6% |
### bootcamp_instructor
| career | count | share |
|---|---|---|
| frontend | 23 | 11.1% |
| backend | 21 | 10.1% |
| data-science | 11 | 5.3% |
| devops | 21 | 10.1% |
| product-manager | 3 | 1.4% |
| ux-designer | 14 | 6.8% |
| fullstack | 12 | 5.8% |
| mobile | 6 | 2.9% |
| data-analyst | 17 | 8.2% |
| machine-learning | 7 | 3.4% |
| ai-engineer | 5 | 2.4% |
| cyber-security | 8 | 3.9% |
| qa-engineer | 25 | 12.1% |
| game-dev | 2 | 1.0% |
| technical-writer | 10 | 4.8% |
| software-architect | 22 | 10.6% |

## Formula-vs-panel agreement (circularity check)

The current hand-authored questionnaire_fit heuristic's top-1 agrees with the panel
consensus on **41.1%** of silver profiles. High agreement means the
learned-vs-formula comparison in Phase 2 is partly circular (the panel may reason
like the hand weights); note this when reading Gate 1 results.

## Confidence

- Mean panel confidence (silver): 0.81
- Mean panel confidence (ambiguous): nan

## Gate 0 checklist

- [ ] Synthetic agreement acceptable (kappa neither near 0 nor suspiciously ~1.0) — see numbers above
- [ ] Label distribution plausible (no career ~0%, none dominating) — see table above
- [ ] Manual sanity check of the sample below passed

## Manual sanity-check sample (20 silver rows)

- **syn_0154** (synthetic) -> backend (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 1, "q3": 3, "q4": 3, "q5": null, "q6": 2, "q7": 0, "q8": 3, "q9": 2, "q10": null, "q11": 0, "q12": 2, "q13": 3, "q15": 3, "q18": 3}`; first explanation: "The person chose 'building the hidden engine that quietly makes everything work' for the tie-breaker question, which points to backend. Additionally, they indicated a preference for solving logical puzzles and ensuring systems never go down, aligning well with backend engineering. The chosen finishing touch of 'tidying up the inside so it's easy to build on later' further supports this decision, a"
- **syn_0008** (synthetic) -> data-analyst (votes 3/3, conf 0.87); answers `{"q1": 1, "q2": 2, "q3": 3, "q4": 2, "q5": 2, "q6": 2, "q7": 3, "q8": 2, "q10": 2, "q11": 2, "q12": 3, "q13": 2, "q16": 0, "q18": 0}`; first explanation: "The candidate chose 'making clear charts and reports that show what happened,' which directly points to data analyst. Additionally, their preference for writing a simple guide when finished something they are proud of further supports the role of a technical writer, but given the strong tie-breaker choice, data analyst is the stronger fit."
- **syn_0066** (synthetic) -> devops (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 3, "q4": 0, "q5": 0, "q6": 0, "q7": 2, "q8": 2, "q10": 1, "q11": 3, "q12": 1, "q13": 0, "q17": 0, "q18": 0}`; first explanation: "The candidate chose 'getting it back up fast and making sure it never happens again' for the tie-breaker question about a website crashing, which aligns with DevOps Engineer responsibilities. Additionally, they preferred writing a simple guide over other options in the second tie-breaker, indicating a preference for documentation and clarity, which is also aligned with Technical Writer's role."
- **syn_0089** (synthetic) -> data-analyst (votes 3/3, conf 0.83); answers `{"q1": 1, "q2": 2, "q3": 0, "q4": 2, "q5": 0, "q6": 2, "q7": 0, "q8": 0, "q10": 2, "q11": 3, "q12": 1, "q13": 0, "q16": 0, "q18": 0}`; first explanation: "The person chose 'making clear charts and reports that show what happened' in the tie-breaker, which directly points to data-analyst. Additionally, their preference for wrangling data to find patterns and producing a report that changes a decision further supports this choice."
- **syn_0159** (synthetic) -> ux-designer (votes 3/3, conf 0.83); answers `{"q1": 3, "q2": 0, "q4": 2, "q5": 2, "q6": null, "q7": 1, "q8": 0, "q9": 3, "q10": 0, "q11": 2, "q12": 2, "q13": 3, "q14": 3, "q18": null}`; first explanation: "The candidate chose 'drawings of how an app should look — someone else can build it' as their tie-breaker answer, which directly aligns with the role of UX Designer. Additionally, they mentioned that visual design is their 'happy place,' further supporting this choice."
- **syn_0002** (synthetic) -> data-science (votes 3/3, conf 0.83); answers `{"q1": 2, "q2": 2, "q3": 1, "q4": 3, "q5": 3, "q6": 3, "q7": 2, "q8": 2, "q10": null, "q11": 0, "q12": 3, "q13": 1, "q16": 1, "q18": 1}`; first explanation: "The individual's chosen tie-breaker option 'digging into messy numbers to figure out why something happened' strongly aligns with the role of a Data Scientist, making top1 'data-science'. The second-best fit is 'machine-learning', as both involve working with data but focus more on model training for predictions in the former and building AI products in the latter."
- **syn_0093** (synthetic) -> ux-designer (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 0, "q4": null, "q5": 2, "q6": 1, "q7": 2, "q8": 0, "q9": 3, "q10": 0, "q11": null, "q12": 3, "q13": 0, "q14": 2, "q18": 0}`; first explanation: "The person chose to make 'a small video game with characters and levels' in the tie-breaker question, which points to 'game-dev'. However, they also selected 'writing a simple guide so anyone can use it' as their preferred finishing touch, indicating a strong preference for documentation and clarity, which aligns more closely with 'technical-writer'. Given that both questions are tied between 'ux-"
- **syn_0128** (synthetic) -> backend (votes 3/3, conf 0.80); answers `{"q1": 0, "q2": null, "q4": 2, "q5": 3, "q6": null, "q7": 0, "q8": 0, "q10": 2, "q11": 1, "q12": 2, "q13": 3, "q18": 1}`; first explanation: 'The person enjoys building stable systems and tends to rally the team, indicating a backend engineer role. Additionally, their desire for insights that drive business impact aligns well with product management.'
- **syn_0011** (synthetic) -> devops (votes 3/3, conf 0.87); answers `{"q1": 2, "q2": 3, "q4": 3, "q5": 1, "q6": 3, "q7": 1, "q8": 3, "q10": 3, "q11": 3, "q12": 2, "q13": 3, "q17": 0, "q18": 0}`; first explanation: "The candidate chose 'getting it back up fast and making sure it never happens again' for the tie-breaker question, which directly points to a DevOps Engineer role. Additionally, they also indicated a preference for writing simple guides, pointing towards a Technical Writer, but their strong emphasis on keeping complex systems running and ensuring zero-downtime deploys further solidifies DevOps as "
- **syn_0141** (synthetic) -> frontend (votes 3/3, conf 0.80); answers `{"q1": 0, "q2": 0, "q4": 1, "q5": 3, "q6": 1, "q7": 1, "q8": 1, "q9": 2, "q10": 2, "q11": 0, "q12": 3, "q13": 1, "q14": 0, "q18": 0}`; first explanation: "The candidate's chosen tie-breakers clearly point towards frontend: they chose to build a website and emphasized writing guides for others to use it, indicating a preference for documentation and user experience. While the technical writer option aligns with their desire for elegant code, the repeated emphasis on creating visible, accessible interfaces and written instructions makes frontend more "
- **syn_0164** (synthetic) -> software-architect (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 3, "q4": 1, "q5": 3, "q6": 0, "q7": 2, "q8": 3, "q10": 1, "q11": 1, "q12": 0, "q13": 3, "q17": 2, "q18": 1}`; first explanation: "The person chose 'redesigning the setup so one failure can't take everything down' for the first tie-breaker, which points to software-architect. For the second tie-breaker, they chose 'showing it to people and hearing what they'd improve,' which indicates a product-manager role. However, the profile strongly emphasizes building infrastructure that everyone depends on, and enjoys shipping clean ma"
- **syn_0023** (synthetic) -> mobile (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 0, "q4": null, "q5": 1, "q6": 2, "q7": 3, "q8": 3, "q9": 2, "q10": 0, "q11": 0, "q12": 2, "q13": 0, "q14": 1, "q18": 2}`; first explanation: "The candidate's choice of 'an app for phones that people carry everywhere' in the tie-breaker question points strongly towards Mobile Developer, as it aligns with their interest in building applications for smartphones. Their preference to focus on making things look and feel perfect further supports this choice, as user interface and experience are key aspects of mobile app development. While Fro"
- **syn_0148** (synthetic) -> qa-engineer (votes 3/3, conf 0.80); answers `{"q1": null, "q2": 1, "q3": 2, "q4": 0, "q5": null, "q6": 2, "q7": null, "q8": 0, "q9": 0, "q10": 2, "q11": 3, "q12": 3, "q13": 3, "q15": 2, "q18": 1}`; first explanation: "The candidate's tie-breaker choice 'trying to break the app on purpose to find problems before users do' directly points to QA Engineer, indicating a strong preference for this role. While they also chose 'showing it to people and hearing what they'd improve' in another question, which could suggest Product Manager, their primary interest seems more aligned with the proactive testing aspect of QA."
- **syn_0198** (synthetic) -> ux-designer (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 0, "q4": 0, "q5": 0, "q6": 0, "q7": 1, "q8": 3, "q9": 3, "q10": 0, "q11": 1, "q12": 0, "q13": 0, "q14": 3, "q18": 2}`; first explanation: "The person chose 'drawings of how an app should look — someone else can build it' in the tie-breaker question, which directly aligns with the role of a UX Designer. Additionally, their preference to show off 'how beautiful and smooth it looks' also supports this choice. The second-best fit is Frontend Developer, as they are very comfortable writing code daily and enjoy making things look perfect."
- **syn_0118** (synthetic) -> ai-engineer (votes 2/3, conf 0.80); answers `{"q1": 2, "q2": 2, "q3": 2, "q4": 2, "q5": 1, "q6": 1, "q7": 0, "q8": 0, "q10": 0, "q11": 0, "q12": 2, "q13": 0, "q16": null, "q18": 2}`; first explanation: "The person chose 'making it look and feel perfect' as their finishing touch, which aligns most closely with the role of an AI Engineer who focuses on the visual and user experience aspects of building products around large language models. While Data Analyst also values aesthetics in their reports, the emphasis on making something visually perfect is more characteristic of AI Engineering."
- **syn_0189** (synthetic) -> cyber-security (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 3, "q4": 3, "q5": 0, "q6": 3, "q7": 0, "q8": 3, "q10": 0, "q11": 0, "q12": 1, "q13": null, "q17": 1, "q18": 3}`; first explanation: "The person chose 'checking whether someone broke in, and locking the doors better' for both tie-breaker questions, which strongly points towards a career focused on security. While they also showed interest in maintaining systems reliability (as indicated by their desire to 'tidy up the inside so it's easy to build on later'), the emphasis on defending against attacks aligns more closely with cybe"
- **syn_0157** (synthetic) -> technical-writer (votes 2/3, conf 0.80); answers `{"q1": 1, "q2": 3, "q4": 1, "q5": 1, "q6": 1, "q7": 2, "q8": 2, "q10": 1, "q11": 1, "q12": 1, "q13": 3, "q17": 2, "q18": 0}`; first explanation: "The candidate chose 'redesigning the setup so one failure can't take everything down' for the question about enjoying fixing a website crash, which aligns with DevOps. However, they also chose 'writing a simple guide so anyone can use it,' which points to Technical Writer as their preferred role. Given the emphasis on writing and making complex technology understandable, Technical Writer is the be"
- **syn_0182** (synthetic) -> data-science (votes 3/3, conf 0.83); answers `{"q1": 0, "q2": 2, "q3": 2, "q4": 0, "q5": null, "q6": 2, "q7": null, "q8": 2, "q10": 2, "q11": 3, "q12": 2, "q13": 3, "q16": 1, "q18": null}`; first explanation: "The individual chose 'digging into messy numbers to figure out why something happened,' which most closely aligns with the Data Scientist role. Although they are equally interested in understanding data, their preference for delving into complex datasets and finding underlying reasons is more characteristic of a Data Scientist than a Data Analyst or other roles."
- **syn_0077** (synthetic) -> fullstack (votes 3/3, conf 0.83); answers `{"q1": 2, "q2": 1, "q3": 3, "q4": 1, "q5": 1, "q6": 1, "q7": 3, "q8": 1, "q9": 1, "q10": 1, "q11": 2, "q12": 3, "q13": 3, "q15": 0, "q18": 0}`; first explanation: "The person chose 'building whole features end to end, from the screen to the data behind it' in the first tie-breaker question, which points directly to fullstack. In the second tie-breaker question, they chose 'writing a simple guide so anyone can use it,' which aligns with technical writer's role of making complex technology understandable through documentation."
- **syn_0068** (synthetic) -> fullstack (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 1, "q3": 2, "q4": 1, "q5": 3, "q6": 3, "q7": 1, "q8": 1, "q9": 0, "q10": 1, "q11": 2, "q12": 0, "q13": 1, "q15": 0, "q18": 0}`; first explanation: "The person chose 'building whole features end to end, from the screen to the data behind it' for their tie-breaker question on team roles, which points to fullstack. Additionally, they showed a strong preference for writing code and solving logical puzzles, which aligns with the role of a backend engineer but more closely matches the fullstack developer's role in owning complete features end-to-en"
