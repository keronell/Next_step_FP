# Question Bank Multi-Label Classification System

Automated multi-label classification system for question bank labeling and analysis.

## Project Structure

```
FinalProjectPrototype/
├── data/                      # Data files
│   ├── question_bank.csv      # Original question bank (input)
│   ├── question_bank_labeled.csv  # Labeled questions (output)
│   └── answers_bank.csv       # Answers bank (future)
│
├── src/                       # Source code / Scripts
│   ├── labeling_pipeline.py   # Main labeling pipeline
│   ├── create_visualizations.py  # Visualization generation
│   └── verify_output.py       # Output verification script
│
├── models/                    # Model files (future)
│   └── README.md              # Models directory documentation
│
├── config/                    # Configuration files
│   └── label_ontology.json    # Label ontology definition
│
├── docs/                      # Documentation
│   ├── LABELING_SYSTEM_SUMMARY.md
│   └── LABEL_DISTRIBUTION_REPORT.md
│
├── visualizations/            # Generated visualizations
│   ├── label_group_distribution.png
│   ├── top_labels_distribution.png
│   ├── labels_per_question_histogram.png
│   ├── category_vs_label_group_heatmap.png
│   └── label_source_distribution.png
│
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Labeling Questions

```bash
# Basic usage (from project root)
python src/labeling_pipeline.py

# With custom paths
python src/labeling_pipeline.py \
    --input data/question_bank.csv \
    --output data/question_bank_labeled.csv \
    --ontology config/label_ontology.json \
    --threshold 0.3

# With embedding-based propagation
python src/labeling_pipeline.py --use-embeddings
```

### Creating Visualizations

```bash
python src/create_visualizations.py
```

Output will be saved to `visualizations/` directory.

### Verifying Output

```bash
python src/verify_output.py
```

## Directory Descriptions

### `/data`
Contains all CSV data files:
- **question_bank.csv**: Original unlabeled questions
- **question_bank_labeled.csv**: Automatically labeled questions (output)
- **answers_bank.csv**: User answers (future)

### `/src`
Python scripts for processing:
- **labeling_pipeline.py**: Main automated labeling system
- **create_visualizations.py**: Generates distribution visualizations
- **verify_output.py**: Validates labeled output

### `/models`
Future directory for machine learning models:
- User classification models
- Label prediction models
- Multi-label classification models

### `/config`
Configuration files:
- **label_ontology.json**: Label definitions, keywords, and weights

### `/docs`
Documentation and reports:
- System summaries
- Analysis reports
- Methodology documentation

### `/visualizations`
Generated charts and graphs (PNG format, 300 DPI):
- Label distributions
- Category mappings
- Source contributions

## Key Features

- ✅ **100% Coverage**: All questions receive at least one label
- ✅ **Multi-label Support**: Average 5.88 labels per question
- ✅ **Abstract Labels**: 37 beginner-friendly, job-agnostic labels
- ✅ **Multiple Sources**: Metadata, rule-based, and embedding-based labeling
- ✅ **Comprehensive Analysis**: Detailed visualizations and reports

## Label Ontology

The system uses 40 abstract labels organized into three groups:

- **Interest Labels** (15): Visual design, user experience, data work, predictive analytics, system building, quality assurance, reliability, security, planning, insights, automation, experimentation, explanation, information presentation, scalable design

- **Trait Labels** (12): Creativity, analytical thinking, attention to detail, collaboration, communication, independence, resilience, empathy, decisiveness, curiosity, organization, flexibility

- **Orientation Labels** (10): Data-oriented, system-oriented, people-focused, business-focused, technology-focused, research-focused, results-focused, excellence-focused, speed-focused, stability-focused

## Acceptance Criteria

✓ ≥90% of questions receive at least one label (achieved: 100%)  
✓ Labels are explainable and traceable to source  
✓ No manual per-question labeling required  
✓ Supports multi-label assignments  
✓ System is iterative and refinable

## Notes

- The labeling system is fully automated and requires no manual intervention
- Labels are abstract and independent of specific job titles
- The system supports iterative refinement of mappings and rules
- Visualizations are diagnostic tools for understanding distributions

## Future Work

- User answer modeling and classification
- Job-role inference using label combinations
- Machine learning models for label prediction
- Integration with answers bank for user classification
