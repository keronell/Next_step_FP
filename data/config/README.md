# config/

Static configuration files that define the label system, field taxonomy, and skill normalization. These are the source of truth for the entire pipeline — changing them requires re-running downstream scripts.

## Files

| File | Description |
|------|-------------|
| `field_taxonomy.json` | 16 canonical tech fields (e.g. `Frontend Development`, `Data Science`). Used by the scraper to classify job postings and by the annotation pipeline as the prediction target space. |
| `label_ontology.json` | 40 abstract labels (Interests, Traits, Orientations) with keyword rules and weights. Drives `scripts/labeling_pipeline.py`. |
| `label_schema.json` | JSON schema definition for the label annotation output format. Used by validators to check structural correctness. |
| `label_schema_examples.jsonl` | Few-shot examples conforming to `label_schema.json`. Used in LLM prompts to guide output format. |
| `skill_aliases.json` | Normalizes raw tag strings to canonical skill names (e.g. `"react.js"` → `"React"`). Used by `scripts/extract_skills.py`. |

## Changing labels or fields

- Adding/removing a field in `field_taxonomy.json` → re-run `scrape_job_ads.py`, `extract_skills.py`, `build_rag.py`, and `answer_questions_local.py`.
- Changing `label_ontology.json` → re-run `labeling_pipeline.py`.
- Do not change canonical field names mid-experiment without versioning — it breaks consistency between training runs.
