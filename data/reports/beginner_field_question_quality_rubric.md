# Beginner Field-Detection Question Quality Rubric

## Purpose
Use this rubric before running large-scale local model annotation so low-quality questions are filtered or revised first.

## Scoring
- Start each question at 100 points.
- Apply penalties per failed check.
- Recommended action thresholds:
  - `82-100`: keep
  - `70-81`: revise
  - `<70`: remove or rewrite

## Required checks
1. Beginner-safe language
   - No unexplained jargon/acronyms.
   - Avoid tool-specific language unless it is defined inside the question.
2. Field discriminativeness
   - Question should help distinguish likely target fields.
   - Avoid generic statements that fit almost every field.
3. Construct alignment
   - Wording must match intended axis from `category`, `subcategory`, and `tags`.
   - Avoid unrelated phrasing that shifts to a different trait/construct.
4. Ambiguity and overlap
   - Avoid vague temporal modifiers (`most of the time`, `overall`, `typically`) unless needed.
   - Avoid near-duplicate template tails (`this describes me well`, `this is true for me`).
5. Leading wording risk
   - Avoid judgmental terms that push agreement (`obviously`, `ideal`, `best`).
6. Answerability for inexperienced users
   - Do not assume prior job/team experience by default.
   - If context is required, phrase as a simple learning scenario.
7. Readability and length
   - Prefer <=24 words and <=180 characters.
   - Use clean sentence case and direct wording.
8. Redundancy control (added check)
   - Detect and down-rank template variants that only change suffixes.
9. Format consistency (added check)
   - Ensure `answer_type` and option formatting are coherent and easy to answer.

## Review workflow
1. Run `python data/scripts/audit_question_quality.py`.
2. Inspect `data/reports/question_bank_beginner_quality_flags.csv`.
3. Triage high severity rows first.
4. Apply revisions/replacements in a patch-ready proposal.
5. Re-run audit until high-severity count is near zero.
