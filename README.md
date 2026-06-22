# NextStep Career Matcher

A prototype career matching system that helps users discover their ideal tech career path through a personalized assessment and generates custom learning roadmaps.

---

## Local API (FastAPI + ChromaDB RAG matching)

> This is the **current** backend for the live React SPA. It connects the existing
> questionnaire to the ChromaDB job-ad vector store and returns explainable career
> recommendations. The Flask/SQLite sections further down describe an older,
> unused architecture.

### What it does

```
React questionnaire  →  POST /api/questionnaire/submit  →  FastAPI
  → build a natural-language profile from the answers
  → query the existing ChromaDB `job_ads` store (per career field)
  → blend semantic similarity + questionnaire fit + skill overlap into a score
  → return top-3 sorted, explainable recommendations  →  rendered in the SPA
```

The 6 careers (frontend, backend, data-science, devops, product-manager,
ux-designer) and their roadmaps are unchanged; each is enriched with RAG signals.

### Prerequisites

- Python 3.12 (a venv already exists at `backend/venv`)
- Node 18+ for the frontend
- The ChromaDB store built from the scraped job ads (step 2 below)

### 1. Install backend dependencies

```bash
backend/venv/bin/python -m pip install -r backend/requirements.txt
```

### 2. Build the ChromaDB store (one-time, uses the existing ingestion pipeline)

```bash
backend/venv/bin/python data/scripts/build_rag.py
```

This embeds ~1575 job ads with `all-MiniLM-L6-v2` into `data/jobs/chroma/`
(collection `job_ads`, cosine space). It is the existing pipeline — not re-written.

### 3. Run the API

```bash
cd backend
venv/bin/python -m uvicorn app.main:app --port 8000
# (optional) copy backend/.env.example -> backend/.env to override defaults
```

Startup logs report the loaded collection size. If the store is missing the API
still starts and serves `/api/health`; `/submit` then returns a safe 503 and the
frontend falls back to an offline estimate.

### 4. Run the frontend against it

```bash
cd frontend
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm install            # first time only
npm run dev            # http://localhost:3000
```

### Example request / response

```bash
curl -s -X POST http://localhost:8000/api/questionnaire/submit \
  -H 'Content-Type: application/json' \
  -d '{"answers":{"q1":3,"q2":2,"q3":3,"q4":2,"q5":2,"q6":2,"q7":2,"q8":2,"q9":1,"q10":2}}'
```

```json
{
  "request_id": "…",
  "recommendations": [
    {
      "id": "data-science", "title": "Data Scientist", "description": "…",
      "keySkills": ["Python","Statistics","Machine Learning","SQL","Data Viz"],
      "icon": "BarChart2", "roadmapKey": "data-science",
      "matchPercent": 66, "score": 0.66,
      "score_breakdown": {"semantic_similarity": 0.31, "questionnaire_fit": 0.75, "skill_overlap": 0.8},
      "reasons": ["Strong alignment with your interests and work style",
                  "Builds on in-demand skills like Python, Statistics, Machine Learning"],
      "matched_skills": ["Python","Statistics","Machine Learning","SQL"],
      "missing_skills": ["R","Data Visualization","Excel","Hadoop"]
    }
  ]
}
```

### Matching formula

```
final = 0.40 * questionnaire_fit + 0.40 * semantic_similarity + 0.20 * skill_overlap
```

- `questionnaire_fit` — ported WEIGHTS+BONUSES from `frontend/src/data.js`, normalized
  relative to the strongest-fitting career.
- `semantic_similarity` — ChromaDB cosine distance converted to `1 - distance`.
- `skill_overlap` — share of a career's key skills present in the retrieved job ads.

Weights live in one place (`backend/app/services/matching_service.py`) and are
asserted to sum to 1. Missing data never earns a component. See that file for the
full documented assumptions.

### Run tests

```bash
cd backend
venv/bin/python -m pytest app/tests -q
```

The tests mock the vector store via a fake repository, so they run without
ChromaDB or the embedding model.

### Environment variables

| Variable | Where | Default | Purpose |
|----------|-------|---------|---------|
| `CHROMA_PATH` | backend | `data/jobs/chroma` | ChromaDB persistence path |
| `CHROMA_COLLECTION` | backend | `job_ads` | Collection name |
| `EMBED_MODEL` | backend | `all-MiniLM-L6-v2` | Must match the store's model |
| `RAG_TOP_K` | backend | `8` | Job ads retrieved per career field |
| `CORS_ORIGINS` | backend | `http://localhost:3000` | Allowed frontend origins |
| `API_PORT` / `LOG_LEVEL` | backend | `8000` / `INFO` | Server config |
| `VITE_API_BASE_URL` | frontend | `http://localhost:8000` | Backend base URL |

### Known limitations

- No persistence yet (submissions/recommendations are not stored).
- No auth.
- Roadmaps are still the static client-side data; not backend-generated.
- Career fields with no matching job ads score on questionnaire fit only.

**Next milestone:** persist submissions, selected careers, and recommendations to
PostgreSQL/Supabase, then add backend roadmap generation.

---

## Features

- **10-Question Assessment**: Personalized questionnaire covering skills, interests, personality, and work style
- **Top 5 Role Matching**: AI-powered matching algorithm that scores users against 22 tech roles
- **Skill Vector Analysis**: Computes user skill levels (0-5 scale) across multiple dimensions
- **Personalized Roadmaps**: Generates 3-5 step learning paths with curated resources
- **Progress Tracking**: Track completion of roadmap items and monitor overall progress

## Tech Stack

### Backend
- Python 3.8+ + Flask
- SQLite (sqlite3)
- RESTful API

### Frontend
- React 18
- React Router
- Vite
- Axios

## Project Structure

```
Next_step_FP/
├── backend/
│   ├── data/
│   │   ├── roles.json          # 22 tech roles with skill requirements
│   │   ├── resources.json      # Learning resources per skill
│   │   └── questions.json      # 10 selected questions with skill mappings
│   ├── db/
│   │   ├── schema.py           # Database schema
│   │   └── __init__.py         # Database connection
│   ├── scripts/
│   │   ├── seed.py             # Database seeding script
│   │   └── generate_data.py    # Data generation script
│   ├── app.py                  # Flask server with APIs
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Landing.jsx     # Landing page
│   │   │   ├── Questionnaire.jsx # Question flow
│   │   │   ├── Results.jsx     # Top 5 roles display
│   │   │   ├── Roadmap.jsx     # Learning roadmap
│   │   │   └── Progress.jsx   # Progress tracking
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── vite.config.js
└── README.md
```

## Setup Instructions

### 1. Install Dependencies

**Backend (Python):**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Frontend (Node.js):**
```bash
cd frontend
npm install
```

### 2. Generate Data Files

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python3 scripts/generate_data.py
```

### 3. Seed Database

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python3 scripts/seed.py
```

This will:
- Create the SQLite database
- Seed 22 roles
- Seed learning resources
- Seed 10 questions

### 4. Start Backend Server

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python3 app.py
```

Server runs on `http://localhost:3001`

### 4. Start Frontend

```bash
cd frontend
npm run dev
```

Frontend runs on `http://localhost:3000`

## API Endpoints

### Sessions
- `POST /api/sessions` - Create a new session
- `POST /api/sessions/:sessionId/answers` - Submit an answer
- `POST /api/sessions/:sessionId/compute` - Compute results and get top 5 roles

### Questions
- `GET /api/questions` - Get all questions

### Roadmaps
- `POST /api/sessions/:sessionId/roadmap` - Generate roadmap for a role
- `GET /api/sessions/:sessionId/roadmap` - Get roadmap with progress
- `PATCH /api/roadmap-items/:itemId` - Update roadmap item status

## Data Model

### Roles
22 tech roles including:
- Frontend, Backend, Full Stack
- QA, DevOps
- Android, iOS
- Software Architect, Technical Writer
- ML Engineer, AI Engineer, Data Scientist
- Data Analyst, BI Analyst, Data Engineer, MLOps
- Product Manager, Engineering Manager
- UX Designer, Cybersecurity

### Skills Taxonomy
Skills are measured on a 0-5 scale:
- 0: No experience
- 1: Beginner
- 2: Basic
- 3: Intermediate
- 4: Advanced
- 5: Expert

### Questions
10 questions mapped to skills with weights:
- Likert5 scale questions
- Single/Multi choice questions
- Numeric input questions

## Matching Algorithm

1. User answers questions
2. System computes skill vector (0-5 for each skill)
3. Each role is scored based on:
   - How well user skills match required skills
   - Weighted by importance of each skill
4. Top 5 roles returned with:
   - Match percentage
   - Key skill gaps
   - Reasons for match

## Roadmap Generation

1. User selects a role
2. System identifies skill gaps
3. Generates 3-5 learning steps:
   - Prioritized by gap size
   - Includes curated resources (1-3 per skill)
   - Links to tutorials, courses, documentation

## Progress Tracking

- Mark roadmap items as completed
- Track overall progress percentage
- View detailed progress breakdown

## MVP Scope

- ✅ 10 questions (expandable to 40)
- ✅ 22 roles (10+ for MVP)
- ✅ Skill taxonomy (0-5 scale)
- ✅ Matching engine
- ✅ Roadmap generator
- ✅ Progress tracking

## Future Enhancements

- Expand to 40 questions
- Add more roles
- Machine learning-based matching
- Social features (share roadmaps)
- Integration with learning platforms
- Advanced analytics

## License

MIT

