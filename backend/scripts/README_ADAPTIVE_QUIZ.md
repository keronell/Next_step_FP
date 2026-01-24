# Adaptive Quiz System - Setup Guide

This guide explains how to set up and use the adaptive quiz system that uses AI agents to generate expert answers and adaptively eliminates jobs as users answer questions.

## Prerequisites

1. **Python 3.8+** installed
2. **OpenAI API Key** - Set as environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
3. **Dependencies installed**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

## Setup Steps

### Step 1: Select Top 10 Jobs

Selects 10 representative jobs from the roles database.

```bash
cd backend/scripts
python3 select_top_jobs.py
```

**Output:** `backend/data/top_10_jobs.json`

**Selected Jobs:**
- Frontend Developer
- Backend Developer
- Full Stack Developer
- Data Scientist
- ML Engineer
- DevOps Engineer
- UX Designer
- Product Manager
- QA Engineer
- Software Architect

---

### Step 2: Generate Expert Answers

Generates expert answers for all questions using AI agents. Each agent acts as an expert in one of the 10 jobs.

**⚠️ Important:** This step makes API calls to OpenAI and may take a while (and cost money). For ~1600 questions × 10 jobs = ~16,000 API calls.

```bash
cd backend/scripts
python3 generate_expert_answers.py
```

**Requirements:**
- `OPENAI_API_KEY` environment variable must be set
- `top_10_jobs.json` must exist (from Step 1)
- `data/data/question_bank.csv` must exist

**Output:** `backend/data/expert_answers.json`

**Progress:** The script shows progress every 10 answers and includes rate limiting (0.5s delay between calls).

**Note:** If interrupted, you can re-run the script. It will overwrite existing answers.

---

### Step 3: Create Expert Database

Creates structured lookup files for efficient querying during the adaptive quiz.

```bash
cd backend/scripts
python3 create_expert_database.py
```

**Requirements:**
- `expert_answers.json` must exist (from Step 2)

**Output:**
- `backend/data/expert_answers_by_question.json` - Lookup by question ID
- `backend/data/expert_answers_by_job.json` - Lookup by job ID

---

### Step 4: Update Database Schema

The database schema has been updated to support adaptive mode. If you have an existing database, you may need to recreate it:

```bash
cd backend
python3 -c "from db import get_db; from db.schema import create_schema; create_schema(get_db())"
```

Or delete the existing database and let it recreate on next run:
```bash
rm backend/data/nextstep.db
```

---

### Step 5: Start the Backend Server

```bash
cd backend
python3 app.py
```

The server will start on `http://localhost:3001`

---

## API Endpoints

### Start Adaptive Quiz

```http
POST /api/adaptive/start
```

**Response:**
```json
{
  "session_id": "uuid",
  "remaining_jobs": 10,
  "question": {
    "id": "5",
    "question": "Most of the time, i enjoy...",
    "answer_type": "Likert5",
    "options": "..."
  }
}
```

### Submit Answer

```http
POST /api/adaptive/<session_id>/answer
Content-Type: application/json

{
  "question_id": "5",
  "answer_value": "4",
  "answer_type": "Likert5"
}
```

**Response (if quiz continues):**
```json
{
  "completed": false,
  "remaining_jobs": 8,
  "questions_answered": 4,
  "warmup_active": false,
  "question": {
    "id": "7",
    "question": "...",
    "answer_type": "Likert5",
    "options": "..."
  }
}
```

**Response (if quiz complete):**
```json
{
  "completed": true,
  "top_5_jobs": [
    {
      "id": "frontend",
      "name": "Frontend Developer",
      "description": "...",
      "required_skills": {...},
      "match_score": 85.3
    },
    ...
  ],
  "questions_answered": 12
}
```

---

## Configuration

Edit `backend/config/adaptive_quiz_config.json` to adjust:

- **warmup_questions**: Number of questions before elimination starts (default: 3)
- **max_questions**: Maximum questions before forced stop (default: 20)
- **min_questions**: Minimum questions before early stop allowed (default: 10)
- **target_jobs_remaining**: Target number of jobs at end (default: 5)
- **elimination_threshold**: Minimum similarity to keep a job (default: 0.3)
- **early_stop_threshold**: Jobs remaining for early stop (default: 7)

---

## How It Works

1. **Warmup Phase (First 3 Questions)**
   - User answers questions
   - No jobs are eliminated
   - All 10 jobs remain in play

2. **Elimination Phase (After Warmup)**
   - Each answer is compared to expert answers
   - Jobs with low similarity scores are eliminated
   - Next question is selected to best differentiate remaining jobs

3. **Stop Conditions**
   - 5 or fewer jobs remaining
   - 20 questions answered
   - 7 or fewer jobs remaining AND 10+ questions answered

4. **Results**
   - Top 5 jobs returned with match scores
   - Scores are similarity percentages (0-100%)

---

## Troubleshooting

### "Top 10 jobs not found"
- Run `select_top_jobs.py` first

### "Expert answers not found"
- Run `generate_expert_answers.py` first
- This requires OpenAI API key

### "Question bank not found"
- Ensure `data/data/question_bank.csv` exists

### API Rate Limits
- The script includes 0.5s delay between calls
- If you hit rate limits, increase the delay in `generate_expert_answers.py`

### Database Schema Issues
- Delete `backend/data/nextstep.db` and recreate
- Or run the schema update manually

---

## File Structure

```
backend/
├── scripts/
│   ├── select_top_jobs.py          # Step 1
│   ├── generate_expert_answers.py  # Step 2
│   ├── create_expert_database.py  # Step 3
│   └── README_ADAPTIVE_QUIZ.md     # This file
├── data/
│   ├── top_10_jobs.json            # Output from Step 1
│   ├── expert_answers.json         # Output from Step 2
│   ├── expert_answers_by_question.json  # Output from Step 3
│   └── expert_answers_by_job.json       # Output from Step 3
├── config/
│   └── adaptive_quiz_config.json   # Configuration
└── app.py                           # API with adaptive endpoints
```

---

## Next Steps

After setting up the adaptive quiz system:

1. **Frontend Integration**: Update frontend to use `/api/adaptive/start` and `/api/adaptive/<session_id>/answer`
2. **Testing**: Test with various answer patterns
3. **Tuning**: Adjust thresholds in config based on results
4. **Optimization**: Consider caching expert answers in memory for faster lookups
