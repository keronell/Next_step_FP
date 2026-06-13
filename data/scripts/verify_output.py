#!/usr/bin/env python3
"""Verify the labeled output file."""

import csv
import json

def verify_output(output_file='data/question_bank_labeled.csv'):
    """Verify the labeled output file."""
    with open(output_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Total questions in output: {len(rows)}")
    
    # Check coverage
    labeled_count = 0
    unlabeled_count = 0
    total_labels = 0
    source_counts = {}
    
    for row in rows:
        labels = json.loads(row['labels'])
        label_scores = json.loads(row['label_scores'])
        label_sources = json.loads(row['label_sources'])
        
        if labels:
            labeled_count += 1
            total_labels += len(labels)
            
            for source in label_sources.values():
                source_counts[source] = source_counts.get(source, 0) + 1
        else:
            unlabeled_count += 1
    
    print(f"\nCoverage Statistics:")
    print(f"  Questions with at least one label: {labeled_count} ({100*labeled_count/len(rows):.1f}%)")
    print(f"  Unlabeled questions: {unlabeled_count}")
    print(f"  Average labels per question: {total_labels/len(rows):.2f}")
    
    print(f"\nSource Distribution:")
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {source}: {count}")
    
    # Show sample
    print(f"\nSample Output (Question ID 1):")
    if rows:
        sample = rows[0]
        print(f"  Question ID: {sample['question_id']}")
        print(f"  Labels: {json.loads(sample['labels'])}")
        scores = json.loads(sample['label_scores'])
        print(f"  Sample Scores:")
        for label, score in list(scores.items())[:3]:
            print(f"    {label}: {score:.3f}")
        sources = json.loads(sample['label_sources'])
        print(f"  Sample Sources:")
        for label, source in list(sources.items())[:3]:
            print(f"    {label}: {source}")
    
    # Check acceptance criteria
    print(f"\nAcceptance Criteria Check:")
    coverage_pct = 100 * labeled_count / len(rows)
    print(f"  ✓ Coverage ≥90%: {'PASS' if coverage_pct >= 90 else 'FAIL'} ({coverage_pct:.1f}%)")
    print(f"  ✓ Labels have sources: {'PASS' if all(json.loads(r['label_sources']) for r in rows if json.loads(r['labels'])) else 'FAIL'}")
    print(f"  ✓ Multi-label support: {'PASS' if any(len(json.loads(r['labels'])) > 1 for r in rows) else 'FAIL'}")
    
    return coverage_pct >= 90

if __name__ == '__main__':
    verify_output()

