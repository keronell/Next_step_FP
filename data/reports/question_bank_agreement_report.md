# Question Bank Agreement Report — LLM Persona Silver Labels

> **These are SILVER labels produced by local LLM personas, not human expert ground
> truth.** Agreement numbers below measure consistency between personas sharing one
> base model (qwen2.5:7b-instruct); they are NOT a human inter-expert noise ceiling. See
> data/docs/NEURAL_MATCHER_DESIGN.md and docs/matching-rework-plan.md for the same
> caveat applied to the career-matcher panel.

Generated: 2026-07-05T16:22:12Z  |  model: `qwen2.5:7b-instruct`  |  prompt: `v4.1.0`  |  temperatures: [0.2, 0.6, 0.9]

## Pool

- Rows on current prompt version (`v4.1.0`): **8640**
- Legacy rows (older prompt versions, target_field was force-injected -- excluded
  from this report): 0

## Target-field confirmation rate (bias check)

Overall confirmation rate: **55.7%** (share of rows where the model's own
`predicted_fields` included the field its persona was assigned to represent, with no
forcing).

| field | confirmation rate |
|---|---|
| Frontend Development | 39.3% |
| Backend Development | 47.0% |
| Full Stack Development | 52.6% |
| Mobile Development | 37.6% |
| Data Analysis | 58.0% |
| Data Science | 59.8% |
| Machine Learning | 45.0% |
| AI Engineering | 54.3% |
| Cyber Security | 59.4% |
| DevOps | 56.3% |
| QA / Software Testing | 68.1% |
| Game Development | 41.7% |
| UI / UX Design | 66.3% |
| Product Management | 77.8% |
| Technical Writing | 80.2% |
| Software Architecture | 48.3% |

No fields flagged below the 50%-of-mean threshold.

## Shared-subset agreement (NOT human agreement)

Complete panels available (same field, same question, all 3 personas answered): **1280**

- Fleiss' kappa (confirmed / not_confirmed, 3 raters): **0.465**
- Cohen's kappa persona_1 vs persona_2: 0.461
- Cohen's kappa persona_1 vs persona_3: 0.474
- Cohen's kappa persona_2 vs persona_3: 0.460

Interpretation caution: personas share one base model, so a high kappa here means
self-consistency, not correctness. A kappa near 1.0 is a flag for persona
non-independence, not a quality guarantee -- same reading as the career panel's report.

## Gate-style checklist

- [ ] No field's confirmation rate is flagged above (no systematic coding-role bias)
- [ ] Fleiss kappa is neither near 0 (personas disagree randomly) nor suspiciously
      near 1.0 (personas are clones despite distinct temperatures)
- [ ] Manual spot check of a handful of rows in `data\answers\question_bank_answered_local.csv` looks reasonable
