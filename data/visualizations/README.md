# visualizations/

Auto-generated diagnostic charts for the label distribution system. All PNGs are produced by `scripts/create_visualizations.py` and should not be manually edited.

## Files

| File | Description |
|------|-------------|
| `label_group_distribution.png` | Bar chart of label counts split by group (Interests / Traits / Orientations) |
| `top_labels_distribution.png` | Top-N most-assigned labels across the question bank |
| `labels_per_question_histogram.png` | Histogram of how many labels each question receives |
| `category_vs_label_group_heatmap.png` | Heatmap of question category × label group co-occurrence |
| `label_source_distribution.png` | Proportion of labels assigned via metadata vs. rule vs. embedding |

## Regenerating

```bash
python data/scripts/create_visualizations.py
```

Charts are written at 300 DPI. Useful for spotting label imbalance or over/under-coverage before training.
