# Quick Local Trust Check Report

- Input file: `data\data\question_bank.csv`
- Sample size requested: `20`
- Sample size executed: `20`
- Model: `qwen2.5:7b-instruct`
- Trust pass rows: `0`
- Trust fail rows: `20`
- Rows with model/parse errors: `20`

## Check pass rates
- json_valid: `0/20`
- schema_valid: `0/20`
- predicted_fields_valid: `0/20`
- field_scores_valid: `0/20`
- target_field_consistency: `0/20`
- confidence_sanity: `0/20`
- likert_score_valid: `0/20`
- format_contradiction_check: `0/20`

## Sample failed rows
- id=`86` | issues=`Model call or JSON parse failed.` | question=`Typically, i enjoy inventing a new way to visualize information. This describes me well.`
- id=`345` | issues=`Model call or JSON parse failed.` | question=`I like problems that require careful reasoning, such as creating a plan for a complex project. (at work)`
- id=`469` | issues=`Model call or JSON parse failed.` | question=`In general, i prefer to work with others on tasks like writing clear documentation for others.`
- id=`511` | issues=`Model call or JSON parse failed.` | question=`Overall, i prefer to work with others on tasks like facilitating a group discussion. This describes me well.`
- id=`325` | issues=`Model call or JSON parse failed.` | question=`Most of the time, i like problems that require careful reasoning, such as optimizing code for performance.`
- id=`873` | issues=`Model call or JSON parse failed.` | question=`I would be productive in an environment where you can experiment and fail safely. This is true for me.`
- id=`1562` | issues=`Model call or JSON parse failed.` | question=`Which domain best matches what you want to do day-to-day?`
- id=`583` | issues=`Model call or JSON parse failed.` | question=`When it matters, i pay attention to details and often check my work for mistakes. This describes me well.`
- id=`581` | issues=`Model call or JSON parse failed.` | question=`Overall, i pay attention to details and often check my work for mistakes. (when things are ambiguous)`
- id=`840` | issues=`Model call or JSON parse failed.` | question=`Most of the time, i would be productive in a research-oriented environment with time for deep work.`

Detailed CSV: `data\reports\quick_trust_check_results.csv`
