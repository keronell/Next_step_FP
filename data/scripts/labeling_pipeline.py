#!/usr/bin/env python3
"""
Automated Multi-Label Question Classification Pipeline

This pipeline assigns abstract labels to questions using:
1. Metadata-based labeling (category, subcategory, tags)
2. Rule-based labeling (keyword/phrase matching)
3. Embedding-based label propagation (similarity-based)
"""

import csv
import json
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import math
import sys

# Try to import optional dependencies
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    print("Warning: sentence-transformers not available. Embedding-based labeling will be skipped.")
    print("Install with: pip install sentence-transformers numpy")


class LabelingPipeline:
    def __init__(self, ontology_path: str, threshold: float = 0.3, embedding_threshold: float = 0.7):
        """
        Initialize the labeling pipeline.
        
        Args:
            ontology_path: Path to label ontology JSON file
            threshold: Minimum confidence score for label inclusion
            embedding_threshold: Minimum similarity for embedding-based labels
        """
        self.threshold = threshold
        self.embedding_threshold = embedding_threshold
        self.ontology = self._load_ontology(ontology_path)
        self.category_mappings = self._build_category_mappings()
        self.subcategory_mappings = self._build_subcategory_mappings()
        self.tag_mappings = self._build_tag_mappings()
        self.rules = self._build_rules()
        
        # Embedding model (lazy load)
        self.embedding_model = None
        self.question_embeddings = None
        
    def _load_ontology(self, path: str) -> Dict:
        """Load label ontology from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _build_category_mappings(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build mappings from categories to labels."""
        mappings = {
            'Personality': [
                ('TRAIT_CREATIVITY', 0.8),
                ('TRAIT_ANALYTICAL', 0.7),
                ('TRAIT_ATTENTION_TO_DETAIL', 0.6),
                ('TRAIT_COLLABORATIVE', 0.6),
                ('TRAIT_COMMUNICATION', 0.6),
            ],
            'Skills': [
                ('TRAIT_CURIOSITY', 0.7),
                ('ORIENTATION_TECHNOLOGY_FOCUSED', 0.8),
            ],
            'Interests': [
                ('ORIENTATION_PEOPLE_FOCUSED', 0.7),
                ('ORIENTATION_TECHNOLOGY_FOCUSED', 0.7),
            ],
            'Values': [
                ('ORIENTATION_BUSINESS_FOCUSED', 0.6),
                ('ORIENTATION_PEOPLE_FOCUSED', 0.6),
                ('TRAIT_EMPATHY', 0.6),
            ],
            'WorkStyle': [
                ('TRAIT_COLLABORATIVE', 0.7),
                ('TRAIT_INDEPENDENCE', 0.7),
                ('TRAIT_ORGANIZATION', 0.6),
                ('TRAIT_FLEXIBILITY', 0.6),
            ],
            'Background': [
                ('TRAIT_CURIOSITY', 0.6),
            ],
            'Habits': [
                ('TRAIT_RESILIENCE', 0.6),
                ('TRAIT_CURIOSITY', 0.6),
            ],
        }
        return mappings
    
    def _build_subcategory_mappings(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build mappings from subcategories to labels."""
        mappings = {
            'Creativity': [('TRAIT_CREATIVITY', 0.9), ('INTEREST_RAPID_EXPERIMENTATION', 0.7), ('INTEREST_VISUAL_DESIGN', 0.6)],
            'Analytical': [('TRAIT_ANALYTICAL', 0.9), ('TRAIT_ATTENTION_TO_DETAIL', 0.7)],
            'Data': [('INTEREST_DATA_WORK', 0.9), ('INTEREST_INSIGHTS_ANALYSIS', 0.8), ('ORIENTATION_DATA_ORIENTED', 0.9)],
            'ML': [('INTEREST_PREDICTIVE_ANALYTICS', 0.95), ('INTEREST_DATA_WORK', 0.7), ('ORIENTATION_RESEARCH_FOCUSED', 0.7)],
            'Programming': [('INTEREST_SYSTEM_BUILDING', 0.8), ('ORIENTATION_SYSTEM_ORIENTED', 0.8), ('TRAIT_ANALYTICAL', 0.6)],
            'TestingQuality': [('INTEREST_QUALITY_ASSURANCE', 0.95), ('TRAIT_ATTENTION_TO_DETAIL', 0.8), ('ORIENTATION_EXCELLENCE_FOCUSED', 0.8)],
            'Security': [('INTEREST_PROTECTION_SECURITY', 0.95), ('TRAIT_ANALYTICAL', 0.7), ('TRAIT_ATTENTION_TO_DETAIL', 0.7)],
            'Web': [('INTEREST_VISUAL_DESIGN', 0.7), ('INTEREST_SYSTEM_BUILDING', 0.6), ('ORIENTATION_PEOPLE_FOCUSED', 0.6)],
            'TechDomains': [('ORIENTATION_TECHNOLOGY_FOCUSED', 0.8), ('TRAIT_CURIOSITY', 0.7)],
            'Tooling': [('INTEREST_AUTOMATION', 0.8), ('ORIENTATION_SYSTEM_ORIENTED', 0.7)],
            'RoleTasks': [('ORIENTATION_PEOPLE_FOCUSED', 0.7), ('ORIENTATION_RESULTS_FOCUSED', 0.7)],
            'Collaboration': [('TRAIT_COLLABORATIVE', 0.9), ('TRAIT_COMMUNICATION', 0.8)],
            'Communication': [('TRAIT_COMMUNICATION', 0.9), ('TRAIT_EMPATHY', 0.7)],
            'Autonomy': [('TRAIT_INDEPENDENCE', 0.9), ('TRAIT_DECISIVENESS', 0.6)],
            'Structure': [('TRAIT_ORGANIZATION', 0.9), ('ORIENTATION_STABILITY_FOCUSED', 0.7)],
            'Constraints': [('TRAIT_FLEXIBILITY', 0.8), ('TRAIT_RESILIENCE', 0.7)],
            'Resilience': [('TRAIT_RESILIENCE', 0.9), ('TRAIT_FLEXIBILITY', 0.7)],
            'Pace': [('ORIENTATION_SPEED_FOCUSED', 0.7), ('TRAIT_FLEXIBILITY', 0.6)],
            'Learning': [('TRAIT_CURIOSITY', 0.9), ('ORIENTATION_RESEARCH_FOCUSED', 0.7)],
            'Growth': [('TRAIT_CURIOSITY', 0.8), ('ORIENTATION_BUSINESS_FOCUSED', 0.7)],
            'Impact': [('ORIENTATION_PEOPLE_FOCUSED', 0.8), ('ORIENTATION_BUSINESS_FOCUSED', 0.7)],
            'Ethics': [('TRAIT_EMPATHY', 0.8), ('ORIENTATION_PEOPLE_FOCUSED', 0.7)],
            'Experience': [('TRAIT_CURIOSITY', 0.7), ('ORIENTATION_RESULTS_FOCUSED', 0.6)],
            'Industry': [('ORIENTATION_BUSINESS_FOCUSED', 0.7), ('TRAIT_CURIOSITY', 0.6)],
            'Activities': [('ORIENTATION_RESULTS_FOCUSED', 0.7), ('TRAIT_COLLABORATIVE', 0.6)],
            'DetailOrientation': [('TRAIT_ATTENTION_TO_DETAIL', 0.9), ('ORIENTATION_EXCELLENCE_FOCUSED', 0.8)],
            'Traits': [('TRAIT_CURIOSITY', 0.7), ('TRAIT_RESILIENCE', 0.6)],
            'RemoteHybrid': [('TRAIT_INDEPENDENCE', 0.7), ('TRAIT_COLLABORATIVE', 0.6), ('TRAIT_FLEXIBILITY', 0.7)],
        }
        return mappings
    
    def _build_tag_mappings(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build mappings from tags to labels."""
        # Tags can be parsed from the tags column (comma-separated)
        # Note: Job-specific tags (like "ML Engineer", "Backend Engineer") map to abstract labels
        mappings = {
            'Personality': [('TRAIT_CREATIVITY', 0.7), ('TRAIT_ANALYTICAL', 0.6)],
            'Creativity': [('TRAIT_CREATIVITY', 0.9)],
            'Data': [('INTEREST_DATA_WORK', 0.8), ('ORIENTATION_DATA_ORIENTED', 0.8)],
            'ML Engineer': [('INTEREST_PREDICTIVE_ANALYTICS', 0.95), ('INTEREST_DATA_WORK', 0.8)],
            'Backend Engineer': [('INTEREST_SYSTEM_BUILDING', 0.95), ('ORIENTATION_SYSTEM_ORIENTED', 0.8)],
            'Frontend Engineer': [('INTEREST_VISUAL_DESIGN', 0.95), ('ORIENTATION_PEOPLE_FOCUSED', 0.8)],
            'DevOps/SRE': [('INTEREST_RELIABILITY_MAINTENANCE', 0.95), ('ORIENTATION_SYSTEM_ORIENTED', 0.8)],
            'Security Engineer': [('INTEREST_PROTECTION_SECURITY', 0.95), ('TRAIT_ANALYTICAL', 0.7)],
            'Product Manager': [('INTEREST_PLANNING_STRATEGY', 0.95), ('ORIENTATION_PEOPLE_FOCUSED', 0.8), ('ORIENTATION_BUSINESS_FOCUSED', 0.8)],
            'UX Designer': [('INTEREST_USER_EXPERIENCE', 0.95), ('ORIENTATION_PEOPLE_FOCUSED', 0.9), ('TRAIT_EMPATHY', 0.8)],
            'QA Engineer': [('INTEREST_QUALITY_ASSURANCE', 0.95), ('TRAIT_ATTENTION_TO_DETAIL', 0.8)],
            'likert': [],  # No specific label for Likert scale type
        }
        return mappings
    
    def _build_rules(self) -> List[Dict]:
        """Build keyword/phrase-based labeling rules."""
        rules = []
        
        # Iterate through ontology to create rules
        for label_type in ['INTEREST_LABELS', 'TRAIT_LABELS', 'ORIENTATION_LABELS']:
            for label_name, label_info in self.ontology[label_type].items():
                keywords = label_info.get('keywords', [])
                weight = label_info.get('weight', 1.0)
                
                # Create regex patterns for keywords (case-insensitive, word boundaries)
                patterns = []
                for keyword in keywords:
                    # Escape special regex characters
                    escaped = re.escape(keyword)
                    # Use word boundaries for better matching
                    patterns.append(rf'\b{escaped}\b')
                
                if patterns:
                    combined_pattern = '|'.join(patterns)
                    rules.append({
                        'label': label_name,
                        'pattern': re.compile(combined_pattern, re.IGNORECASE),
                        'weight': weight * 0.8,  # Rule-based weights are slightly lower
                        'keywords': keywords  # Store keywords for reference
                    })
        
        return rules
    
    def _apply_metadata_labels(self, category: str, subcategory: str, tags: str) -> Dict[str, Tuple[float, str]]:
        """
        Apply labels based on metadata (category, subcategory, tags).
        
        Returns:
            Dict mapping label_name to (confidence_score, source)
        """
        labels = {}
        
        # Category-based labels
        if category in self.category_mappings:
            for label, weight in self.category_mappings[category]:
                labels[label] = (weight, 'metadata')
        
        # Subcategory-based labels (higher weight than category)
        if subcategory in self.subcategory_mappings:
            for label, weight in self.subcategory_mappings[subcategory]:
                # Use max to combine with category-based scores
                if label in labels:
                    labels[label] = (max(labels[label][0], weight), 'metadata')
                else:
                    labels[label] = (weight, 'metadata')
        
        # Tag-based labels
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            for tag in tag_list:
                if tag in self.tag_mappings:
                    for label, weight in self.tag_mappings[tag]:
                        if label in labels:
                            # Average with existing score for tag-based labels
                            labels[label] = ((labels[label][0] + weight) / 2, 'metadata')
                        else:
                            labels[label] = (weight, 'metadata')
        
        return labels
    
    def _apply_rule_labels(self, question_text: str) -> Dict[str, Tuple[float, str]]:
        """
        Apply labels based on keyword/phrase rules in question text.
        
        Returns:
            Dict mapping label_name to (confidence_score, source)
        """
        labels = {}
        question_lower = question_text.lower()
        
        for rule in self.rules:
            matches = rule['pattern'].findall(question_text)
            if matches:
                # Calculate score based on number of matches (capped at rule weight)
                match_count = len(matches)
                # Multiple matches increase confidence slightly
                score = min(rule['weight'] * (1 + 0.1 * (match_count - 1)), 1.0)
                score = min(score, rule['weight'])
                
                if rule['label'] in labels:
                    # Use max score if multiple rules match same label
                    labels[rule['label']] = (max(labels[rule['label']][0], score), 'rule')
                else:
                    labels[rule['label']] = (score, 'rule')
        
        return labels
    
    def _aggregate_labels(self, *label_dicts: Dict[str, Tuple[float, str]]) -> Dict[str, Tuple[float, str]]:
        """
        Aggregate labels from multiple sources.
        
        Uses weighted average for same label from different sources:
        - metadata: weight 1.0
        - rule: weight 0.8
        - embedding: weight 0.7
        
        Returns:
            Dict mapping label_name to (final_confidence_score, source)
        """
        aggregated = {}
        source_weights = {'metadata': 1.0, 'rule': 0.8, 'embedding': 0.7}
        
        for label_dict in label_dicts:
            for label, (score, source) in label_dict.items():
                if label in aggregated:
                    # Weighted average with source weights
                    existing_score, existing_source = aggregated[label]
                    existing_weight = source_weights.get(existing_source, 0.5)
                    new_weight = source_weights.get(source, 0.5)
                    
                    # Combined score: weighted average, then normalize
                    total_weight = existing_weight + new_weight
                    combined_score = (existing_score * existing_weight + score * new_weight) / total_weight
                    
                    # Track primary source (metadata > rule > embedding)
                    source_priority = {'metadata': 3, 'rule': 2, 'embedding': 1}
                    primary_source = existing_source if source_priority.get(existing_source, 0) >= source_priority.get(source, 0) else source
                    
                    aggregated[label] = (min(combined_score, 1.0), primary_source)
                else:
                    aggregated[label] = (score, source)
        
        return aggregated
    
    def _normalize_scores(self, labels: Dict[str, Tuple[float, str]]) -> Dict[str, Tuple[float, str]]:
        """
        Normalize label scores.
        Currently just ensures scores are in [0, 1] range and filters by threshold.
        """
        normalized = {}
        for label, (score, source) in labels.items():
            if score >= self.threshold:
                normalized[label] = (score, source)
        return normalized
    
    def label_question(self, question_id: str, category: str, subcategory: str, 
                      question: str, tags: str = "") -> Dict:
        """
        Label a single question using all available methods.
        
        Returns:
            Dict with labels, scores, and sources
        """
        # Apply metadata-based labeling
        metadata_labels = self._apply_metadata_labels(category, subcategory, tags)
        
        # Apply rule-based labeling
        rule_labels = self._apply_rule_labels(question)
        
        # Aggregate labels
        aggregated = self._aggregate_labels(metadata_labels, rule_labels)
        
        # Normalize and filter by threshold
        final_labels = self._normalize_scores(aggregated)
        
        # Format output
        return {
            'question_id': question_id,
            'labels': sorted([label for label in final_labels.keys()]),
            'label_scores': {label: score for label, (score, _) in final_labels.items()},
            'label_sources': {label: source for label, (_, source) in final_labels.items()},
        }
    
    def process_questions(self, input_csv: str, output_csv: str, use_embeddings: bool = False):
        """
        Process all questions from CSV and generate labeled output.
        
        Args:
            input_csv: Path to input question bank CSV
            output_csv: Path to output labeled questions CSV
            use_embeddings: Whether to use embedding-based label propagation
        """
        results = []
        questions_data = []
        
        # Read all questions
        print(f"Reading questions from {input_csv}...")
        with open(input_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                questions_data.append(row)
        
        print(f"Processing {len(questions_data)} questions...")
        
        # Process each question with metadata and rule-based labeling
        for i, row in enumerate(questions_data):
            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(questions_data)} questions...")
            
            result = self.label_question(
                question_id=row['id'],
                category=row.get('category', ''),
                subcategory=row.get('subcategory', ''),
                question=row.get('question', ''),
                tags=row.get('tags', '')
            )
            results.append(result)
        
        # Apply embedding-based label propagation if requested
        if use_embeddings and HAS_EMBEDDINGS:
            print("Applying embedding-based label propagation...")
            results = self._apply_embedding_propagation(questions_data, results)
        
        # Write results
        print(f"Writing results to {output_csv}...")
        self._write_results(output_csv, results)
        
        # Print statistics
        self._print_statistics(results)
        
        return results
    
    def _apply_embedding_propagation(self, questions_data: List[Dict], results: List[Dict]) -> List[Dict]:
        """
        Apply embedding-based label propagation to increase coverage.
        """
        if self.embedding_model is None:
            print("  Loading embedding model...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("  Computing question embeddings...")
        questions = [row.get('question', '') for row in questions_data]
        self.question_embeddings = self.embedding_model.encode(questions, show_progress_bar=True)
        
        print("  Propagating labels based on similarity...")
        # Find high-confidence seed questions for each label
        label_seeds = defaultdict(list)
        for i, result in enumerate(results):
            for label, score in result['label_scores'].items():
                if score >= 0.8:  # High-confidence threshold
                    label_seeds[label].append(i)
        
        # Propagate labels to similar questions
        for i, result in enumerate(results):
            for label, seed_indices in label_seeds.items():
                if label in result['labels']:
                    continue  # Already has this label
                
                # Find max similarity to any seed question for this label
                max_sim = 0.0
                for seed_idx in seed_indices:
                    if i != seed_idx:  # Don't compare to self
                        similarity = self._cosine_similarity(
                            self.question_embeddings[i],
                            self.question_embeddings[seed_idx]
                        )
                        max_sim = max(max_sim, similarity)
                
                # Add label if similarity exceeds threshold
                if max_sim >= self.embedding_threshold:
                    embedding_score = max_sim * 0.7  # Scale down embedding scores
                    if embedding_score >= self.threshold:
                        result['labels'].append(label)
                        result['label_scores'][label] = embedding_score
                        result['label_sources'][label] = 'embedding'
            
            # Sort labels after processing all propagations
            result['labels'] = sorted(result['labels'])
        
        return results
    
    def _cosine_similarity(self, vec1, vec2):
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    def _write_results(self, output_csv: str, results: List[Dict]):
        """Write results to CSV file."""
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['question_id', 'labels', 'label_scores', 'label_sources']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                # Convert dicts to JSON strings for CSV storage
                writer.writerow({
                    'question_id': result['question_id'],
                    'labels': json.dumps(result['labels']),
                    'label_scores': json.dumps(result['label_scores']),
                    'label_sources': json.dumps(result['label_sources']),
                })
    
    def _print_statistics(self, results: List[Dict]):
        """Print labeling statistics."""
        total = len(results)
        labeled_count = sum(1 for r in results if r['labels'])
        label_counts = defaultdict(int)
        source_counts = defaultdict(int)
        total_labels = 0
        
        for result in results:
            for label in result['labels']:
                label_counts[label] += 1
                total_labels += 1
            for source in result['label_sources'].values():
                source_counts[source] += 1
        
        print("\n" + "="*60)
        print("LABELING STATISTICS")
        print("="*60)
        print(f"Total questions: {total}")
        print(f"Questions with at least one label: {labeled_count} ({100*labeled_count/total:.1f}%)")
        print(f"Average labels per question: {total_labels/total:.2f}")
        print(f"\nLabel distribution (top 15):")
        for label, count in sorted(label_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
            print(f"  {label}: {count} ({100*count/total:.1f}%)")
        print(f"\nSource distribution:")
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count}")
        print("="*60)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated question labeling pipeline')
    parser.add_argument('--input', default='data/question_bank.csv', help='Input CSV file')
    parser.add_argument('--output', default='data/question_bank_labeled.csv', help='Output CSV file')
    parser.add_argument('--ontology', default='config/label_ontology.json', help='Label ontology JSON file')
    parser.add_argument('--threshold', type=float, default=0.3, help='Minimum confidence threshold')
    parser.add_argument('--embedding-threshold', type=float, default=0.7, help='Embedding similarity threshold')
    parser.add_argument('--use-embeddings', action='store_true', help='Enable embedding-based label propagation')
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = LabelingPipeline(
        ontology_path=args.ontology,
        threshold=args.threshold,
        embedding_threshold=args.embedding_threshold
    )
    
    # Process questions
    pipeline.process_questions(
        input_csv=args.input,
        output_csv=args.output,
        use_embeddings=args.use_embeddings
    )
    
    print(f"\n✓ Labeling complete! Results written to {args.output}")


if __name__ == '__main__':
    main()

