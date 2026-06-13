# Synthetic Output Validation Report

- Input file: `data\data\question_bank_answered_local.csv`
- Total rows: `32`

## Core Checks
- Valid `predicted_fields` JSON rows: `32/32`
- Valid `field_scores_json` JSON rows: `32/32`
- Valid top-k rows (3-5 canonical fields): `32/32`
- Valid score dictionaries (all 16 fields + sums to ~1): `32/32`
- Confidence in [0,1]: `32/32`
- Mean confidence (valid rows): `0.2`
- Rows with non-empty `error`: `0`

## Likert5 Score Check
- Likert5 rows: `30`
- Likert5 rows with score in [1..5]: `8/30`

## Field Coverage (predicted_fields frequency)
- Frontend Development: `26`
- Backend Development: `25`
- Full Stack Development: `4`
- Mobile Development: `2`
- Data Analysis: `9`
- Data Science: `5`
- Machine Learning: `3`
- AI Engineering: `2`
- Cyber Security: `2`
- DevOps: `2`
- QA / Software Testing: `2`
- Game Development: `2`
- UI / UX Design: `5`
- Product Management: `2`
- Technical Writing: `2`
- Software Architecture: `3`

## Target Field Coverage (generation guarantee)
- Target field valid rows: `32/32`
- Rows where `target_field` appears in `predicted_fields`: `32/32`
- Minimum samples required per field: `2`
- Frontend Development: `2`
- Backend Development: `2`
- Full Stack Development: `2`
- Mobile Development: `2`
- Data Analysis: `2`
- Data Science: `2`
- Machine Learning: `2`
- AI Engineering: `2`
- Cyber Security: `2`
- DevOps: `2`
- QA / Software Testing: `2`
- Game Development: `2`
- UI / UX Design: `2`
- Product Management: `2`
- Technical Writing: `2`
- Software Architecture: `2`
- Fields below minimum target samples: `[]`

## Persona Diversity by Field
- Frontend Development: `2` unique personas
- Backend Development: `2` unique personas
- Full Stack Development: `2` unique personas
- Mobile Development: `2` unique personas
- Data Analysis: `2` unique personas
- Data Science: `2` unique personas
- Machine Learning: `2` unique personas
- AI Engineering: `2` unique personas
- Cyber Security: `2` unique personas
- DevOps: `2` unique personas
- QA / Software Testing: `2` unique personas
- Game Development: `2` unique personas
- UI / UX Design: `2` unique personas
- Product Management: `2` unique personas
- Technical Writing: `2` unique personas
- Software Architecture: `2` unique personas
- Fields with low persona diversity: `[]`

## Sample Failed Rows (up to 20)
- No parse failures detected.

Raw JSON summary: `data\reports\synthetic_output_validation_report.json`
