import asyncio
import json
import csv
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from pydantic import BaseModel
from ollama import AsyncClient
from tqdm.asyncio import tqdm

# --- CONFIGURATION ---
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
BACKEND_DATA = BACKEND_DIR / 'data'
DATA_DATA = PROJECT_ROOT / 'data' / 'data'

MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b')
MAX_CONCURRENT_TASKS = 4  # Safe for 12GB VRAM; increase to 8 if speed is too slow
CHECKPOINT_FILE = BACKEND_DATA / 'expert_answers_checkpoint.json'
FINAL_OUTPUT = BACKEND_DATA / 'expert_answers.json'
QUESTIONS_CSV = DATA_DATA / 'question_bank.csv'
JOBS_JSON = BACKEND_DATA / 'top_10_jobs.json'

# --- DATA MODELS ---
class ExpertResponse(BaseModel):
    """Enforces Ollama to return a JSON object like {"answer": "4"}"""
    answer: str

# --- CORE UTILITIES ---
def load_data():
    """Load your existing source files."""
    if not QUESTIONS_CSV.exists():
        raise FileNotFoundError(
            f"Question bank not found at: {QUESTIONS_CSV}\n"
            f"Expected location: {DATA_DATA / 'question_bank.csv'}"
        )
    if not JOBS_JSON.exists():
        raise FileNotFoundError(
            f"Top 10 jobs file not found at: {JOBS_JSON}\n"
            f"Expected location: {BACKEND_DATA / 'top_10_jobs.json'}\n"
            f"Run 'python3 select_top_jobs.py' first to create this file."
        )
    
    questions = []
    with open(QUESTIONS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(row)
    
    with open(JOBS_JSON, 'r') as f:
        jobs = json.load(f)
    
    print(f"✓ Loaded {len(questions)} questions and {len(jobs)} jobs")
    return questions, jobs

def load_checkpoint() -> List[Dict]:
    """Load results from a previous run to resume progress."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_checkpoint(results: List[Dict]):
    """Saves current progress to a temporary file."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

# --- ASYNC LOGIC ---
async def process_question(client: AsyncClient, job: Dict, q: Dict, semaphore: asyncio.Semaphore):
    """Single expert generation task using Structured Output."""
    async with semaphore:
        skills = ", ".join(job.get('required_skills', {}).keys())
        
        system_prompt = f"You are an expert {job['name']}. Answer authentically and ONLY with the final value."
        
        user_prompt = f"""Expert Context: {job['description']}
Key Skills: {skills}

Question: {q['question']}
Type: {q['answer_type']}
Options: {q.get('options', 'N/A')}

Perspective: As a {job['name']}, provide:
1. Likert5: A digit 1-5.
2. Choice: The exact text from Options.
3. Numeric: A realistic number.

Value (ONLY the value):"""

        try:
            # Leveraging 2026 Structured Output feature
            response = await client.chat(
                model=MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                format=ExpertResponse.model_json_schema(),
                options={'temperature': 0.1, 'stop': ["\n"]}
            )
            
            # Parse response content - handle both JSON and plain text
            content = response.message.content
            if isinstance(content, str):
                try:
                    content_dict = json.loads(content)
                except json.JSONDecodeError:
                    # If not JSON, try to extract Likert5 value or use as-is
                    if q['answer_type'] == 'Likert5':
                        match = re.search(r'[1-5]', content)
                        content_dict = {"answer": match.group() if match else "3"}
                    else:
                        content_dict = {"answer": content.strip()}
            else:
                content_dict = content
            
            data = ExpertResponse(**content_dict)
            return {
                "job_id": job['id'],
                "job_name": job['name'],
                "question_id": q['id'],
                "answer": data.answer,
                "answer_type": q['answer_type']
            }
        except Exception as e:
            # Silently log errors; the checkpoint system allows retries on next run
            return None

async def check_ollama_server():
    """Check if Ollama server is running and accessible."""
    try:
        client = AsyncClient()
        await asyncio.wait_for(client.list(), timeout=2.0)
        return True
    except Exception as e:
        print(f"\n❌ ERROR: Cannot connect to Ollama server!")
        print(f"   Error: {str(e)[:100]}")
        print(f"\n   SOLUTION: Start Ollama server in another terminal:")
        print(f"   $ ollama serve")
        print(f"\n   Then run this script again.\n")
        return False

async def main():
    print("Checking Ollama server connection...")
    if not await check_ollama_server():
        return
    print(f"✓ Connected to Ollama server")
    print(f"✓ Using model: {MODEL}\n")
    
    questions, jobs = load_data()
    results = load_checkpoint()
    
    # Create a lookup set of (job_id, question_id) to skip already processed items
    processed_keys = {f"{r['job_id']}:{r['question_id']}" for r in results}

    client = AsyncClient()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    # Build list of pending tasks
    tasks = []
    for job in jobs:
        for q in questions:
            if f"{job['id']}:{q['id']}" not in processed_keys:
                tasks.append(process_question(client, job, q, semaphore))

    if not tasks:
        print("🎉 No new questions to process. Dataset is complete!")
        return

    print(f"🚀 Processing {len(tasks)} tasks via {MODEL}...")
    
    # tqdm.as_completed provides a live progress bar for async tasks
    count = 0
    for task in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Expert Answers"):
        answer = await task
        if answer:
            results.append(answer)
            count += 1
            
            # Checkpoint every 50 responses to secure progress
            if count % 50 == 0:
                save_checkpoint(results)

    # Final conversion and cleanup
    FINAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(FINAL_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Generation complete. Total rows: {len(results)}")
    print(f"📂 File: {FINAL_OUTPUT}")
    
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink() # Remove checkpoint after successful completion

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user. Progress saved to checkpoint.")