# Synthetic Output Validation Report

- Input file: `data\answers\question_bank_answered_local.csv`
- Total rows: `8640`

## Core Checks
- Valid `predicted_fields` JSON rows: `8640/8640`
- Valid `field_scores_json` JSON rows: `8640/8640`
- Valid top-k rows (3-5 canonical fields): `8640/8640`
- Valid score dictionaries (all 16 fields + sums to ~1): `8640/8640`
- Confidence in [0,1]: `8640/8640`
- Mean confidence (valid rows): `0.8505`
- Rows with non-empty `error`: `0`

## Likert5 Score Check
- Likert5 rows: `7178`
- Likert5 rows with score in [1..5]: `6568/7178`

## Field Coverage (predicted_fields frequency)
- Frontend Development: `917`
- Backend Development: `1484`
- Full Stack Development: `793`
- Mobile Development: `234`
- Data Analysis: `1113`
- Data Science: `1652`
- Machine Learning: `1209`
- AI Engineering: `531`
- Cyber Security: `608`
- DevOps: `648`
- QA / Software Testing: `781`
- Game Development: `291`
- UI / UX Design: `3363`
- Product Management: `5732`
- Technical Writing: `5753`
- Software Architecture: `811`

## Target Field Coverage (generation guarantee)
- Target field valid rows: `8640/8640`
- Rows where `target_field` appears in `predicted_fields`: `4815/8640`
- Minimum samples required per field: `2`
- Frontend Development: `540`
- Backend Development: `540`
- Full Stack Development: `540`
- Mobile Development: `540`
- Data Analysis: `540`
- Data Science: `540`
- Machine Learning: `540`
- AI Engineering: `540`
- Cyber Security: `540`
- DevOps: `540`
- QA / Software Testing: `540`
- Game Development: `540`
- UI / UX Design: `540`
- Product Management: `540`
- Technical Writing: `540`
- Software Architecture: `540`
- Fields below minimum target samples: `[]`

## Persona Diversity by Field
- Frontend Development: `3` unique personas
- Backend Development: `3` unique personas
- Full Stack Development: `3` unique personas
- Mobile Development: `3` unique personas
- Data Analysis: `3` unique personas
- Data Science: `3` unique personas
- Machine Learning: `3` unique personas
- AI Engineering: `3` unique personas
- Cyber Security: `3` unique personas
- DevOps: `3` unique personas
- QA / Software Testing: `3` unique personas
- Game Development: `3` unique personas
- UI / UX Design: `3` unique personas
- Product Management: `3` unique personas
- Technical Writing: `3` unique personas
- Software Architecture: `3` unique personas
- Fields with low persona diversity: `[]`

## Sample Failed Rows (up to 20)
- No parse failures detected.

Raw JSON summary: `data\reports\synthetic_output_validation_report.json`
