# questions/

The question bank — the core input to the field-prediction system.

## Files

| File | Description |
|------|-------------|
| `question_bank.csv` | 1,611 questions across categories: Personality, Skills, WorkStyle, Interests. Each row has `id`, `category`, `subcategory`, `question`, `answer_type`, `options`, `tags`. |
| `question_bank_labeled.csv` | Auto-generated multi-label annotations for every question. Each row has `question_id`, `labels` (JSON array), `label_scores` (JSON dict), `label_sources` (JSON dict). Produced by `scripts/labeling_pipeline.py`. |

## Label sources

Each label in `question_bank_labeled.csv` is traced to one of three sources:
- `metadata` — derived from `category`/`subcategory`/`tags` columns
- `rule` — matched by keyword rules in `config/label_ontology.json`
- `embedding` — propagated via semantic similarity (when `--use-embeddings` flag is used)

## Regenerating labels

```bash
python data/scripts/labeling_pipeline.py
# or with embedding propagation:
python data/scripts/labeling_pipeline.py --use-embeddings
```
