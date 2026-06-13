#!/usr/bin/env python3
"""
Create structured database from expert answers for efficient querying.
"""
import json
from pathlib import Path
from collections import defaultdict


def create_expert_database():
    """Create structured database of expert answers"""
    expert_answers_file = Path(__file__).parent.parent / 'data' / 'expert_answers.json'
    
    if not expert_answers_file.exists():
        print(f"Error: {expert_answers_file} not found.")
        print("Run generate_expert_answers.py first to generate expert answers.")
        return None
    
    print(f"Loading expert answers from {expert_answers_file}...")
    
    with open(expert_answers_file, 'r', encoding='utf-8') as f:
        expert_answers = json.load(f)
    
    print(f"Loaded {len(expert_answers)} expert answer entries")
    
    # Structure: {question_id: {job_id: answer}}
    question_to_job_answers = defaultdict(dict)
    
    # Structure: {job_id: {question_id: answer}}
    job_to_question_answers = defaultdict(dict)
    
    for entry in expert_answers:
        q_id = str(entry['question_id'])
        job_id = entry['job_id']
        answer = entry['answer']
        
        question_to_job_answers[q_id][job_id] = answer
        job_to_question_answers[job_id][q_id] = answer
    
    # Save both structures
    output_dir = Path(__file__).parent.parent / 'data'
    
    by_question_file = output_dir / 'expert_answers_by_question.json'
    by_job_file = output_dir / 'expert_answers_by_job.json'
    
    with open(by_question_file, 'w', encoding='utf-8') as f:
        json.dump(dict(question_to_job_answers), f, indent=2, ensure_ascii=False)
    
    with open(by_job_file, 'w', encoding='utf-8') as f:
        json.dump(dict(job_to_question_answers), f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Expert database created")
    print(f"  - Questions: {len(question_to_job_answers)}")
    print(f"  - Jobs: {len(job_to_question_answers)}")
    print(f"  - Saved to:")
    print(f"    * {by_question_file}")
    print(f"    * {by_job_file}")
    
    # Show some stats
    if job_to_question_answers:
        first_job = list(job_to_question_answers.keys())[0]
        print(f"\n  Sample: Job '{first_job}' has {len(job_to_question_answers[first_job])} answers")
    
    return {
        'by_question': dict(question_to_job_answers),
        'by_job': dict(job_to_question_answers)
    }


if __name__ == '__main__':
    create_expert_database()
