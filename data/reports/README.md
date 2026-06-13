# reports/

Quality audit outputs, trust-check results, and validation summaries. All files here are generated — do not edit manually.

## Files

| File | Produced by | Description |
|------|-------------|-------------|
| `synthetic_output_validation_report.md` | `validate_synthetic_output.py` | Human-readable structural validation of `answers/question_bank_answered_local.csv` |
| `synthetic_output_validation_report.json` | `validate_synthetic_output.py` | Machine-readable version of the same report |
| `quick_trust_check_report.md` | `quick_trust_check_local.py` | Fast trust-check report on a small sample (schema, field consistency, Likert validity) |
| `quick_trust_check_results.csv` | `quick_trust_check_local.py` | Per-row trust-check results for the sampled questions |
| `step3_label_schema_report.md` | labeling pipeline | Summary of label schema coverage after Step 3 of labeling |
| `question_bank_step2_data_quality_report.md` | audit script | Data quality flags from Step 2 of question bank processing |
| `question_bank_beginner_quality_summary.md` | `audit_question_quality.py` | Summary of beginner-level question quality metrics |
| `question_bank_beginner_quality_flags.csv` | `audit_question_quality.py` | Per-question flags for beginner quality issues |
| `beginner_field_question_quality_rubric.md` | audit script | Rubric used to score beginner question quality |
| `question_revision_proposal.md` | audit script | Suggested revisions for flagged low-quality questions |

## Acceptance thresholds

- `predicted_fields` JSON valid ≥ 99% of rows
- `field_scores_json` valid ≥ 99% of rows
- Likert score valid ≥ 99% of Likert rows
- Non-empty `error` rows ≤ 1%
- Quick trust pass rate ≥ 90%
