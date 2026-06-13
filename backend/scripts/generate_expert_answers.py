#!/usr/bin/env python3
"""
Generate expert answers for all questions using AI agents.
Each agent acts as an expert in one of the top 10 jobs.
"""
import csv
import json
import os
import time
import re
from pathlib import Path
from typing import List, Dict

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed.")
    print("Install it with: pip install openai")
    exit(1)


def load_questions(csv_path: Path) -> List[Dict]:
    """Load all questions from question bank CSV"""
    questions = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(row)
    return questions


def create_expert_prompt(job: Dict, question: Dict) -> str:
    """Create prompt for AI agent to answer as job expert"""
    skills = ', '.join(job['required_skills'].keys()) if 'required_skills' in job else 'N/A'
    
    return f"""You are an expert {job['name']} with deep experience in this role.

Job Description: {job['description']}
Required Skills: {skills}

Question: {question['question']}
Question Type: {question['answer_type']}
Options: {question.get('options', 'N/A')}

Answer this question from the perspective of a {job['name']}. 
Be authentic and reflect how someone in this role would genuinely respond.

For Likert5 questions, respond with ONLY a number 1-5 (1=Strongly disagree, 5=Strongly agree).
For SingleChoice/MultiChoice, select the most appropriate option(s) exactly as shown in the options.
For Numeric questions, provide a realistic number.

Your answer (ONLY the answer, no explanation):"""


def generate_expert_answer(job: Dict, question: Dict, client: OpenAI) -> str:
    """Generate answer using AI agent"""
    prompt = create_expert_prompt(job, question)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": f"You are an expert {job['name']}. Answer questions authentically from this role's perspective."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=50  # Keep answers concise
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Clean up answer - extract just the number or option
        if question['answer_type'] == 'Likert5':
            # Extract first number 1-5
            match = re.search(r'[1-5]', answer)
            if match:
                answer = match.group()
            else:
                # Default to neutral if can't parse
                answer = '3'
        elif question['answer_type'] in ['SingleChoice', 'MultiChoice']:
            # Try to extract from options
            options = question.get('options', '')
            if options:
                # Look for option in the answer
                option_parts = options.split(';')
                for part in option_parts:
                    if part.strip().lower() in answer.lower():
                        answer = part.strip()
                        break
        
        return answer
    except Exception as e:
        print(f"API Error: {e}")
        raise


def generate_all_expert_answers():
    """Generate expert answers for all jobs and questions"""
    project_root = Path(__file__).parent.parent.parent
    question_bank = project_root / 'data' / 'data' / 'question_bank.csv'
    top_jobs_file = Path(__file__).parent.parent / 'data' / 'top_10_jobs.json'
    
    # Check files exist
    if not question_bank.exists():
        print(f"Error: Question bank not found at {question_bank}")
        return None
    
    if not top_jobs_file.exists():
        print(f"Error: Top 10 jobs file not found. Run select_top_jobs.py first.")
        return None
    
    # Load data
    print("Loading questions and jobs...")
    questions = load_questions(question_bank)
    with open(top_jobs_file, 'r') as f:
        jobs = json.load(f)
    
    print(f"Loaded {len(questions)} questions and {len(jobs)} jobs")
    
    # Load API key and create client
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = OpenAI(api_key=api_key)
    
    expert_answers = []
    total = len(jobs) * len(questions)
    current = 0
    
    print(f"\nGenerating {total} expert answers...")
    print("This may take a while. Progress will be shown every 10 answers.\n")
    
    for job in jobs:
        print(f"\n{'='*60}")
        print(f"Processing: {job['name']}")
        print(f"{'='*60}")
        
        for question in questions:
            current += 1
            try:
                answer = generate_expert_answer(job, question, client)
                expert_answers.append({
                    'job_id': job['id'],
                    'job_name': job['name'],
                    'question_id': question['id'],
                    'question': question['question'],
                    'answer': answer,
                    'answer_type': question['answer_type']
                })
                
                if current % 10 == 0:
                    percent = (current * 100) // total
                    print(f"Progress: {current}/{total} ({percent}%)")
                
                # Rate limiting - be nice to API
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error for {job['name']}, Q{question['id']}: {e}")
                # Continue with next question
                continue
    
    # Save to JSON file
    output_file = Path(__file__).parent.parent / 'data' / 'expert_answers.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(expert_answers, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"✓ Generated {len(expert_answers)} expert answers")
    print(f"✓ Saved to {output_file}")
    print(f"{'='*60}")
    
    # Show summary
    if len(expert_answers) < total:
        print(f"Warning: Expected {total} answers, got {len(expert_answers)}")
        print("Some answers may have failed. Check errors above.")
    
    return expert_answers


if __name__ == '__main__':
    try:
        generate_all_expert_answers()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Partial results may be saved.")
    except Exception as e:
        print(f"\nError: {e}")
        exit(1)
