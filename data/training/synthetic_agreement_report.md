# Synthetic Agreement Report — LLM Panel Silver Labels

> **These are SILVER labels produced by a local LLM panel, not human expert ground
> truth.** All agreement numbers below measure consistency between LLM personas
> sharing one base model (qwen2.5:7b-instruct); they are NOT a human inter-expert noise
> ceiling and must never be presented as expert validation.

Generated: 2026-07-18T16:26:14Z  |  model: `qwen2.5:7b-instruct`  |  prompt: `panel-v2.1.0`  |  temperatures: hiring_manager=0.2, career_counselor=0.6, bootcamp_instructor=0.9

## Pool

- Profiles labeled (complete 3-persona panels): **237** (7 real from public.submissions, 230 synthetic-generated)
- Incomplete panels dropped: 0
- Failed votes (after retries): 0
- **NOTE:** public.submissions held only 7 real submissions at labeling time, so the
  pool is dominated by generated synthetic profiles (seeded/mixed/random over the
  answer space, adaptive branching respected). `profile_source` distinguishes them.

## Consensus filtering (>= 2/3 personas agree on top-1)

- High-consensus -> `silver_labels.parquet`: **232** (unanimous: 193)
- Low-agreement -> `ambiguous_labels.parquet`: **5**

## Synthetic agreement (NOT human agreement)

- Fleiss' kappa (3 personas, 16 careers): **0.857**
- Cohen's kappa hiring_manager vs career_counselor: 0.875
- Cohen's kappa hiring_manager vs bootcamp_instructor: 0.843
- Cohen's kappa career_counselor vs bootcamp_instructor: 0.853

Interpretation caution: personas share one base model, so high kappa here means
self-consistency, not correctness. Near-perfect kappa would be a red flag for
persona non-independence rather than a quality guarantee.

## Label distribution (silver consensus top-1)

| career | count | share |
|---|---|---|
| frontend | 47 | 20.3% |
| backend | 15 | 6.5% |
| data-science | 15 | 6.5% |
| devops | 18 | 7.8% |
| product-manager | 6 | 2.6% |
| ux-designer | 12 | 5.2% |
| fullstack | 13 | 5.6% |
| mobile | 8 | 3.4% |
| data-analyst | 17 | 7.3% |
| machine-learning | 15 | 6.5% |
| ai-engineer | 9 | 3.9% |
| cyber-security | 11 | 4.7% |
| qa-engineer | 16 | 6.9% |
| game-dev | 5 | 2.2% |
| technical-writer | 11 | 4.7% |
| software-architect | 14 | 6.0% |

## Per-persona top-1 distribution (all complete panels)

### hiring_manager
| career | count | share |
|---|---|---|
| frontend | 56 | 23.6% |
| backend | 17 | 7.2% |
| data-science | 15 | 6.3% |
| devops | 18 | 7.6% |
| product-manager | 6 | 2.5% |
| ux-designer | 12 | 5.1% |
| fullstack | 11 | 4.6% |
| mobile | 8 | 3.4% |
| data-analyst | 17 | 7.2% |
| machine-learning | 15 | 6.3% |
| ai-engineer | 9 | 3.8% |
| cyber-security | 11 | 4.6% |
| qa-engineer | 16 | 6.8% |
| game-dev | 3 | 1.3% |
| technical-writer | 9 | 3.8% |
| software-architect | 14 | 5.9% |
### career_counselor
| career | count | share |
|---|---|---|
| frontend | 42 | 17.7% |
| backend | 15 | 6.3% |
| data-science | 15 | 6.3% |
| devops | 18 | 7.6% |
| product-manager | 6 | 2.5% |
| ux-designer | 23 | 9.7% |
| fullstack | 12 | 5.1% |
| mobile | 7 | 3.0% |
| data-analyst | 17 | 7.2% |
| machine-learning | 15 | 6.3% |
| ai-engineer | 9 | 3.8% |
| cyber-security | 11 | 4.6% |
| qa-engineer | 16 | 6.8% |
| game-dev | 5 | 2.1% |
| technical-writer | 12 | 5.1% |
| software-architect | 14 | 5.9% |
### bootcamp_instructor
| career | count | share |
|---|---|---|
| frontend | 41 | 17.3% |
| backend | 11 | 4.6% |
| data-science | 16 | 6.8% |
| devops | 18 | 7.6% |
| product-manager | 7 | 3.0% |
| ux-designer | 15 | 6.3% |
| fullstack | 16 | 6.8% |
| mobile | 7 | 3.0% |
| data-analyst | 16 | 6.8% |
| machine-learning | 15 | 6.3% |
| ai-engineer | 9 | 3.8% |
| cyber-security | 11 | 4.6% |
| qa-engineer | 15 | 6.3% |
| game-dev | 15 | 6.3% |
| technical-writer | 11 | 4.6% |
| software-architect | 14 | 5.9% |

## Formula-vs-panel agreement (circularity check)

The current hand-authored questionnaire_fit heuristic's top-1 agrees with the panel
consensus on **52.2%** of silver profiles. High agreement means the
learned-vs-formula comparison in Phase 2 is partly circular (the panel may reason
like the hand weights); note this when reading Gate 1 results.

## Confidence

- Mean panel confidence (silver): 0.81
- Mean panel confidence (ambiguous): 0.81

## Gate 0 checklist

- [ ] Synthetic agreement acceptable (kappa neither near 0 nor suspiciously ~1.0) — see numbers above
- [ ] Label distribution plausible (no career ~0%, none dominating) — see table above
- [ ] Manual sanity check of the sample below passed

## Manual sanity-check sample (20 silver rows)

- **syn_c0205_game-dev** (synthetic) -> ux-designer (votes 2/3, conf 0.83); answers `{"q1": 3, "q2": 0, "q4": null, "q5": 1, "q6": 1, "q7": 0, "q8": null, "q9": 3, "q10": 3, "q11": 3, "q12": 2, "q13": 2, "q14": 2, "q18": 2}`; first explanation: "The candidate chose 'making it look and feel perfect' as their finishing touch, which strongly aligns with the role of UX Designer. Additionally, they expressed a strong preference for visual design and described making things look beautiful and polished, further supporting this choice. While both frontend and UX Designer roles involve creating visually appealing interfaces, the tie-breaker answer"
- **syn_0059** (synthetic) -> cyber-security (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 3, "q4": 3, "q5": 1, "q6": 1, "q7": 0, "q8": 2, "q10": 0, "q11": 3, "q12": 3, "q13": 3, "q17": 1, "q18": 0}`; first explanation: "The candidate chose 'checking whether someone broke in, and locking the doors better' for the crash scenario, which points to cyber-security. Additionally, they indicated a preference for writing simple guides for others to use, which aligns with technical writing but is less strongly indicated by their other answers compared to their focus on system reliability. The tie-breaker questions are deci"
- **syn_0002** (synthetic) -> data-science (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 2, "q3": 3, "q4": 1, "q5": 1, "q6": 1, "q7": 2, "q8": 1, "q10": 3, "q11": 3, "q12": 3, "q13": 2, "q16": 1, "q18": 0}`; first explanation: "The candidate's preference to 'dig into messy numbers to figure out why something happened' aligns most closely with the role of a Data Scientist, as indicated by their tie-breaker answer. Additionally, they expressed excitement about wrangling data to find patterns and showing off surprising discoveries in the numbers, which further supports this choice. The other tie-breaker option 'writing a si"
- **syn_0164** (synthetic) -> cyber-security (votes 3/3, conf 0.80); answers `{"q1": 0, "q2": 3, "q4": 0, "q5": 3, "q6": 1, "q7": 3, "q8": 2, "q10": 0, "q11": 2, "q12": 2, "q13": 1, "q17": 1, "q18": 3}`; first explanation: "The individual chose 'checking whether someone broke in, and locking the doors better' for the first tie-breaker question, which directly points to cybersecurity analyst. For the second tie-breaker question, they chose 'tidying up the inside so it's easy to build on later,' which aligns with the role of a software architect who focuses on internal design and scalability. However, since they priori"
- **syn_0008** (synthetic) -> data-analyst (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 2, "q3": 3, "q4": 3, "q5": 2, "q6": 2, "q7": 2, "q8": 2, "q10": 2, "q11": 2, "q12": 2, "q13": 2, "q16": 0, "q18": 0}`; first explanation: "The candidate chose 'making clear charts and reports that show what happened' in the tie-breaker question, which directly aligns with the role of a Data Analyst. Additionally, their preference for writing code with guidance, curiosity about data stories, and pride in insights that drive business impact further support a strong fit for Data Analyst. The second-best fit is Data Scientist as they sha"
- **syn_0195** (synthetic) -> devops (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 3, "q4": 3, "q5": 3, "q6": 1, "q7": 1, "q8": 3, "q10": 0, "q11": null, "q12": 2, "q13": 3, "q17": 0, "q18": 3}`; first explanation: "The person chose 'getting it back up fast and making sure it never happens again' in the tie-breaker question, which directly points to DevOps Engineer. Additionally, their preference for 'tidying up the inside so it's easy to build on later' also aligns well with a Software Architect role, as they are focused on maintaining and scaling systems. However, the urgency of restoring a system and ensur"
- **syn_0018** (synthetic) -> data-science (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 2, "q3": 1, "q4": 2, "q5": 2, "q6": 1, "q7": 1, "q8": 1, "q10": 2, "q11": null, "q12": 3, "q13": 2, "q16": 1, "q18": 0}`; first explanation: "The person chose 'digging into messy numbers to figure out why something happened' for the tie-breaker question, which points directly to data-science. They also mentioned that they are more excited about 'wrangling data to find patterns' and their ideal work output is 'a report that changes a decision,' both of which align closely with the responsibilities of a Data Scientist. The second choice, "
- **syn_0191** (synthetic) -> software-architect (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 3, "q4": 2, "q5": 2, "q6": 3, "q7": 1, "q8": 1, "q10": 1, "q11": 1, "q12": 1, "q13": 2, "q17": 2, "q18": 1}`; first explanation: "The candidate chose 'redesigning the setup so one failure can't take everything down' for the first tie-breaker, indicating a preference for designing robust systems that can handle failures gracefully. For the second tie-breaker, they chose to 'show it to people and hearing what they'd improve', which aligns more closely with the role of a Product Manager in gathering feedback from users and stak"
- **syn_0148** (synthetic) -> data-analyst (votes 3/3, conf 0.80); answers `{"q1": null, "q2": 2, "q3": 1, "q4": 2, "q5": 2, "q6": 1, "q7": 2, "q8": 3, "q10": 0, "q11": 2, "q12": 0, "q13": 0, "q16": 0, "q18": 0}`; first explanation: "The user chose 'making clear charts and reports that show what happened' as the most satisfying option, which points to data-analyst. Additionally, their preference for writing a simple guide so anyone can use it further supports data-analyst, as creating documentation is a key activity in this role."
- **syn_0120** (synthetic) -> devops (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 3, "q4": 0, "q5": 1, "q6": 0, "q7": 0, "q8": 0, "q10": 0, "q11": 0, "q12": 1, "q13": 1, "q17": 0, "q18": 0}`; first explanation: "The candidate chose 'getting it back up fast and making sure it never happens again' for the crash scenario, which points to DevOps. Additionally, they selected 'writing a simple guide so anyone can use it' as their preferred finishing touch, indicating a preference for documentation and ease of use, which aligns more closely with Technical Writing."
- **syn_c0202_game-dev** (synthetic) -> frontend (votes 2/3, conf 0.80); answers `{"q1": null, "q2": 0, "q4": 0, "q5": null, "q6": 1, "q7": 1, "q8": 1, "q9": 3, "q10": 0, "q11": null, "q12": 2, "q13": 1, "q14": 2, "q18": 2}`; first explanation: "The candidate chose to 'make a small video game with characters and levels' for the tie-breaker question, which points towards game-dev. However, they also indicated that their finishing touch would be 'making it look and feel perfect', which aligns more closely with frontend development or UX design. Given their preference for visual design and creating polished products, frontend development is "
- **syn_0012** (synthetic) -> qa-engineer (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 1, "q3": 1, "q4": 1, "q5": 3, "q6": 1, "q7": 1, "q8": 1, "q9": 1, "q10": 1, "q11": 2, "q12": 3, "q13": 3, "q15": 2, "q18": 0}`; first explanation: "The person chose to 'try to break the app on purpose to find problems before users do' for the tie-breaker question, which directly points to QA Engineer. Additionally, their preference to 'writing a simple guide so anyone can use it' aligns more with Technical Writer, but this was not their top choice in the specific scenario given. Their comfort with code and interest in debugging suggest a stro"
- **syn_0090** (synthetic) -> ai-engineer (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 2, "q3": 2, "q4": 0, "q5": 1, "q6": 1, "q7": 2, "q8": 1, "q10": 0, "q11": 2, "q12": 3, "q13": 1, "q16": 3, "q18": 0}`; first explanation: "The person chose 'building an app around a smart AI assistant or chatbot' for the tie-breaker question, which directly points to the ai-engineer role. Additionally, they indicated a preference for writing a simple guide so anyone can use it as their finishing touch, which aligns more with technical-writing than any of the other roles in this shortlist. Therefore, ai-engineer is the top recommendat"
- **syn_0172** (synthetic) -> qa-engineer (votes 3/3, conf 0.83); answers `{"q1": 3, "q2": 3, "q4": 3, "q5": null, "q6": 0, "q7": null, "q8": 2, "q10": 2, "q11": 3, "q12": 1, "q13": 3, "q17": 3, "q18": 2}`; first explanation: "The individual chose 'writing the checks that would have caught the problem before launch' in the tie-breaker question, which directly points to QA Engineer. Additionally, their desire to make a system that never goes down and their enjoyment of keeping complex systems running align more closely with the responsibilities of a QA Engineer."
- **syn_0169** (synthetic) -> software-architect (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 1, "q3": 1, "q4": 2, "q5": 0, "q6": 0, "q7": 2, "q8": 1, "q9": 2, "q10": 3, "q11": 3, "q12": 1, "q13": 3, "q15": 1, "q18": 2}`; first explanation: "The individual chose 'drawing the big blueprint that everyone else builds on' for the tie-breaker question, which aligns with the software-architect role. Additionally, their preference for zero-downtime deploys and a focus on reliability in high-pressure situations (like keeping a site online during a holiday sale) further supports this choice."
- **syn_0131** (synthetic) -> ux-designer (votes 3/3, conf 0.80); answers `{"q1": 3, "q2": 0, "q4": 2, "q5": 0, "q6": 0, "q7": 0, "q8": 2, "q9": 0, "q10": 2, "q11": 0, "q12": 1, "q13": 0, "q14": 3, "q18": 0}`; first explanation: "The individual's choice of 'drawing how an app should look — someone else can build it' for the tie-breaker question points towards UX Designer, as they are focusing on the visual and user experience aspects without needing to code the application themselves. Their preference for writing a simple guide also aligns more closely with Technical Writer, but given their comfort in creating beautiful an"
- **syn_0140** (synthetic) -> cyber-security (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 3, "q4": 0, "q5": 3, "q6": 2, "q7": null, "q8": 3, "q10": 3, "q11": 3, "q12": 2, "q13": 0, "q17": 1, "q18": 0}`; first explanation: "The person chose 'checking whether someone broke in, and locking the doors better' for both tie-breaker questions, which strongly points towards a career focused on security and incident response, making Cybersecurity Analyst the top choice. The second-best fit is DevOps Engineer as they also indicated a strong interest in maintaining system reliability and preventing failures."
- **syn_0023** (synthetic) -> frontend (votes 3/3, conf 0.83); answers `{"q1": 3, "q2": 0, "q4": 1, "q5": 1, "q6": 0, "q7": 1, "q8": 1, "q9": 2, "q10": 2, "q11": 3, "q12": 2, "q13": 0, "q14": 1, "q18": 2}`; first explanation: 'The person chose to build an app for phones that people carry everywhere, which points towards the mobile career. However, they also emphasized making it look and feel perfect as their finishing touch of pride, which aligns more closely with frontend development. Given their comfort with code and preference for visual beauty, frontend remains their top choice.'
- **syn_c0303_game-dev** (synthetic) -> frontend (votes 3/3, conf 0.80); answers `{"q1": 1, "q2": 0, "q4": 0, "q5": 0, "q6": 0, "q7": 3, "q8": 3, "q9": 0, "q10": 0, "q11": 0, "q12": 0, "q13": 3, "q14": 2, "q18": 2}`; first explanation: "The candidate's choice of building a small video game with characters and levels for the first tie-breaker question points towards 'game-dev', but their preference to make it look and feel perfect for the second tie-breaker question aligns more closely with 'frontend'. Given that they enjoy making things visually appealing, are comfortable in an environment with lots of collaboration, and prioriti"
- **syn_0179** (synthetic) -> qa-engineer (votes 3/3, conf 0.80); answers `{"q1": 2, "q2": 1, "q3": 1, "q4": 1, "q5": 1, "q6": 2, "q7": 1, "q8": 0, "q9": 0, "q10": 0, "q11": 1, "q12": 2, "q13": 0, "q15": 2, "q18": 1}`; first explanation: "The candidate chose 'trying to break the app on purpose to find problems before users do' for the tie-breaker question, which directly points to QA Engineer. Additionally, their preference to show off how beautiful and smooth a project looks aligns more with roles that ensure reliability and performance under load, such as a Software Architect who focuses on designing systems that survive scale an"
