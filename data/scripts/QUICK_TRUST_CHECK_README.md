# Quick Local Trust-Check Workflow

## Goal
Run a fast local check on a small question sample to decide whether generated answers are trustworthy before full runs.

## What it checks
- JSON validity
- Schema adherence
- Predicted field list constraints
- Field-score structure checks
- Target-field consistency
- Confidence sanity range
- Likert score compatibility
- Simple contradiction/format sanity

## Commands

1) Fast trust check on small sample:

```bash
python data/scripts/quick_trust_check_local.py --sample-size 20 --timeout-s 60
```

2) Dry-run without calling Ollama (pipeline check only):

```bash
python data/scripts/quick_trust_check_local.py --sample-size 20 --skip-model-call
```

3) Use a different local model:

```bash
python data/scripts/quick_trust_check_local.py --sample-size 20 --model qwen3:14b --timeout-s 90
```

## Outputs
- `data/reports/quick_trust_check_results.csv`
- `data/reports/quick_trust_check_report.md`

## Suggested acceptance rule
- Trust pass rate >= 90% on quick sample
- JSON/schema validity >= 95%
- Target-field consistency >= 85%

If below threshold, tune prompt or model before full generation.
