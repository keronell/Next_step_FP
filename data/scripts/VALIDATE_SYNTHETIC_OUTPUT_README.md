# Synthetic Output Validator Guide

## What this script does
Script: `data/scripts/validate_synthetic_output.py`

It validates the quality and schema consistency of:
- `data/data/question_bank_answered_local.csv`

It checks:
- JSON parseability of `predicted_fields` and `field_scores_json`
- `predicted_fields` quality (must be 3-5 unique canonical fields)
- `field_scores_json` quality (must include all 16 canonical fields, each in `[0,1]`, and total approx `1.0`)
- `confidence` validity (`[0,1]`)
- `Likert5` rows have valid scores in `1..5`
- count of rows with non-empty `error`
- field coverage frequency across predicted results
- sample failed rows (up to 20) for quick manual inspection

## Output files
After running, it writes:
- `data/reports/synthetic_output_validation_report.md` (human-readable report)
- `data/reports/synthetic_output_validation_report.json` (machine-readable summary)

## How to run
From project root:

```powershell
python data\scripts\validate_synthetic_output.py
```

## Recommended usage loop
1. Run `answer_questions_local.py` to generate synthetic annotations.
2. Run this validator.
3. Review:
   - parse failure rows
   - low confidence patterns
   - weak field coverage
4. Fix prompt/schema settings and re-run generation.
5. Repeat until validation quality is acceptable.

## Pass criteria (suggested for experiment)
- `predicted_fields` JSON valid in >= 99% rows
- `field_scores_json` valid in >= 99% rows
- top-k validity in >= 99% rows
- score-dict validity in >= 99% rows
- Likert score validity in >= 99% Likert rows
- non-empty `error` rows <= 1%

## Notes
- This validator checks structural reliability, not semantic correctness.
- Keep manual review for semantic quality on a sampled subset.
