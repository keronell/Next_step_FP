# NextStep Career Matcher

A prototype career matching system that helps users discover their ideal tech career path through a personalized assessment and generates custom learning roadmaps.

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

