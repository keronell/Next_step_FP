# data/

All data, configuration, scripts, and generated outputs for the NextStep field-prediction system.

## Directory overview

| Directory | Purpose |
|-----------|---------|
| `questions/` | The question bank — original questions and their auto-generated labels |
| `answers/` | Synthetic persona answers used for model training and validation |
| `jobs/` | Scraped job postings (raw JSON) and the ChromaDB RAG vector store |
| `config/` | Static configuration: label ontology, field taxonomy, skill aliases, schema |
| `scripts/` | All Python scripts — data collection, labeling, annotation, validation |
| `models/` | Placeholder for trained model artifacts (future) |
| `visualizations/` | Generated distribution charts (PNG) |
| `reports/` | Quality audit reports, trust-check results, validation summaries |
| `docs/` | Design documents, architecture notes, implementation instructions |

## Data flow

```
jobs/raw/*.json  ←  scripts/scrape_job_ads.py
       ↓
scripts/extract_skills.py  →  adds skills[] to raw JSONs
       ↓
scripts/build_rag.py  →  jobs/chroma/  (vector store)

questions/question_bank.csv
       ↓
scripts/labeling_pipeline.py  →  questions/question_bank_labeled.csv
       ↓
scripts/answer_questions_local.py  →  answers/question_bank_answered_local.csv
       ↓
scripts/validate_synthetic_output.py  →  reports/
```

## Quick start

```bash
pip install -r requirements.txt   # from project root

# Scrape jobs and build RAG
python data/scripts/scrape_job_ads.py
python data/scripts/extract_skills.py
python data/scripts/build_rag.py

# Label questions
python data/scripts/labeling_pipeline.py

# Generate synthetic answers
python data/scripts/answer_questions_local.py

# Validate output
python data/scripts/validate_synthetic_output.py
python data/scripts/quick_trust_check_local.py --sample-size 20
```
