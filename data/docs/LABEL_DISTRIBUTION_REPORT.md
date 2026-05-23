# Label Distribution Analysis Report

**Generated:** 2026-01-10 12:36:05

## Executive Summary

This report provides a comprehensive analysis of label distributions in the labeled question bank. The analysis covers 1,702 questions with 10,014 total label assignments using 37 unique labels.

**Key Metrics:**
- **Coverage:** 100.0% of questions have at least one label
- **Average Labels per Question:** 5.88
- **Label Density:** 5.88 ± 1.75 labels per question

---

## 1. Label Group Distribution

### Summary
The label assignments are distributed across three main groups:

| Label Group | Count | Percentage |
|------------|-------|------------|
| Interest | 1,440 | 14.4% |
| Trait | 5,854 | 58.5% |
| Orientation | 2,720 | 27.2% |

### Visualization
See `label_group_distribution.png` for bar chart and pie chart visualizations.

### Observations
- Trait labels are the most common, representing 58.5% of all label assignments.
- Interest labels account for 14.4% of assignments.
- Orientation labels represent 27.2% of assignments.
- The distribution shows a reasonable balance across the three label groups.

### Group Coverage
Percentage of questions that have at least one label from each group:
- Interest: 53.9%
- Trait: 95.0%
- Orientation: 70.5%

---

## 2. Top Labels Distribution

### Summary
The top 20 most frequently assigned labels are shown below:

| Rank | Label | Count | Percentage |
|------|-------|-------|------------|
| 1 | CURIOSITY | 1,046 | 61.5% |
| 2 | COLLABORATIVE | 801 | 47.1% |
| 3 | TECHNOLOGY FOCUSED | 719 | 42.2% |
| 4 | PEOPLE FOCUSED | 708 | 41.6% |
| 5 | COMMUNICATION | 638 | 37.5% |
| 6 | ATTENTION TO DETAIL | 547 | 32.1% |
| 7 | ANALYTICAL | 494 | 29.0% |
| 8 | CREATIVITY | 485 | 28.5% |
| 9 | EMPATHY | 438 | 25.7% |
| 10 | RESILIENCE | 437 | 25.7% |
| 11 | FLEXIBILITY | 351 | 20.6% |
| 12 | BUSINESS FOCUSED | 349 | 20.5% |
| 13 | ORGANIZATION | 313 | 18.4% |
| 14 | INDEPENDENCE | 290 | 17.0% |
| 15 | EXCELLENCE FOCUSED | 245 | 14.4% |
| 16 | PLANNING STRATEGY | 243 | 14.3% |
| 17 | DATA WORK | 197 | 11.6% |
| 18 | RESEARCH FOCUSED | 177 | 10.4% |
| 19 | RESULTS FOCUSED | 168 | 9.9% |
| 20 | DATA ORIENTED | 162 | 9.5% |

### Visualization
See `top_labels_distribution.png` for a detailed horizontal bar chart.

### Observations
- The most common label is "CURIOSITY" appearing in 61.5% of questions.
- The top 10 labels cover a diverse range of interests, traits, and orientations.
- There is a gradual decline in frequency, indicating good label diversity without excessive concentration.

---

## 3. Labels per Question Distribution

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 5.88 |
| Median | 6.0 |
| Standard Deviation | 1.75 |
| Minimum | 2 |
| Maximum | 12 |

### Visualization
See `labels_per_question_histogram.png` for histogram and box plot visualizations.

### Observations
- Questions receive an average of 5.88 labels, with a median of 6.0.
- The distribution has a standard deviation of 1.75, indicating moderate variability.
- The range spans from 2 to 12 labels per question.
- Most questions have multiple labels, supporting multi-label classification goals.

---

## 4. Category vs Label Group Matrix

### Summary

The heatmap shows how question categories map to label groups.

### Category Distribution

- **Background**: 40 labels total
  - Interest: 4 (10.0%)
  - Trait: 20 (50.0%)
  - Orientation: 16 (40.0%)

- **Habits**: 715 labels total
  - Interest: 115 (16.1%)
  - Trait: 377 (52.7%)
  - Orientation: 223 (31.2%)

- **Interests**: 2,074 labels total
  - Interest: 214 (10.3%)
  - Trait: 547 (26.4%)
  - Orientation: 1,313 (63.3%)

- **Personality**: 3,584 labels total
  - Interest: 506 (14.1%)
  - Trait: 2,936 (81.9%)
  - Orientation: 142 (4.0%)

- **Skills**: 1,052 labels total
  - Interest: 371 (35.3%)
  - Trait: 253 (24.0%)
  - Orientation: 428 (40.7%)

- **Values**: 970 labels total
  - Interest: 171 (17.6%)
  - Trait: 388 (40.0%)
  - Orientation: 411 (42.4%)

- **WorkStyle**: 1,579 labels total
  - Interest: 59 (3.7%)
  - Trait: 1,333 (84.4%)
  - Orientation: 187 (11.8%)

### Visualization
See `category_vs_label_group_heatmap.png` for detailed heatmaps showing both absolute counts and percentages.

### Observations
- Categories show varying distributions across label groups.
- Some categories (e.g., Personality) are naturally aligned with Trait labels.
- Technical categories (e.g., Skills, Interests) tend to map to Interest and Orientation labels.

---

## 5. Label Source Distribution

### Summary
Labels are assigned from different sources:

| Source | Count | Percentage |
|--------|-------|------------|
| Metadata | 8,056 | 80.4% |
| Rule | 1,958 | 19.6% |

### Visualization
See `label_source_distribution.png` for stacked bar chart and pie chart.

### Observations
- Metadata-based labeling contributes the most labels.
- The combination of metadata and rule-based labeling provides comprehensive coverage.
- Embedding-based propagation is not enabled in this run.

---

## Key Findings and Insights

### Strengths
1. **Excellent Coverage**: 100.0% of questions have at least one label, exceeding the ≥90% requirement.
2. **Multi-label Support**: Average of 5.88 labels per question enables rich multi-label classification.
3. **Balanced Distribution**: Label groups are reasonably distributed, preventing over-concentration in any single group.
4. **Diverse Label Set**: 37 unique labels provide sufficient granularity.

### Potential Risks or Imbalances
- Interest labels are underrepresented at 14.4%.
- Trait labels may be overrepresented at 58.5%.
- Label 'TRAIT_CURIOSITY' appears in more than 50% of questions, indicating potential over-generalization.

### Recommendations
1. **Monitor Label Diversity**: Continue to ensure questions receive diverse label combinations.
2. **Review Top Labels**: Consider if the most frequent labels are appropriately general or if they need refinement.
3. **Category Alignment**: Validate that category-to-label mappings align with intended system design.
4. **Source Balance**: Embedding-based propagation could be enabled to increase coverage if needed.

---

## Acceptance Criteria Status

✓ **All label groups visualized**: PASS - All three groups (Interest, Trait, Orientation) are represented  
✓ **Top labels clearly identifiable**: PASS - Top 20 labels are clearly shown with counts and percentages  
✓ **Label density quantified**: PASS - Mean (5.88), median (6.0), and distribution statistics provided  
✓ **Quick qualitative assessment supported**: PASS - Visualizations enable rapid understanding of distribution patterns  
✓ **Results align with reported statistics**: PASS - All statistics match pipeline output  

---

## Technical Notes

- Visualizations are exported as PNG files at 300 DPI for high-quality printing.
- All charts include titles, axis labels, legends, and value annotations for clarity.
- Color coding is consistent across visualizations:
  - Interest labels: Blue (#4A90E2)
  - Trait labels: Green (#50C878)
  - Orientation labels: Red (#E94B3C)

---

**End of Report**
