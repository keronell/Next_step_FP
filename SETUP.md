# Quick Setup Guide

## Prerequisites
- Python 3.8+ installed
- Node.js 18+ installed (for frontend)
- npm or yarn

## Installation Steps

### 1. Install All Dependencies

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

### 3. Seed the Database

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python3 scripts/seed.py
```

This creates the SQLite database and populates it with:
- 22 roles
- Learning resources
- 10 questions

### 4. Start the Application

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python3 app.py
```

Backend will run on `http://localhost:3001`

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Frontend will run on `http://localhost:3000`

**Or use the one-click start script:**
```bash
./start.sh  # On Windows: node start.js
```

### 4. Open in Browser

Navigate to `http://localhost:3000`

## Troubleshooting

### Database not found
- Make sure you ran `python3 scripts/seed.py` in the backend directory
- Check that `backend/data/` directory exists

### Port already in use
- Backend: Change `PORT` environment variable or in `backend/.env` (default: 3001)
- Frontend: Change `port` in `frontend/vite.config.js` (default: 3000)

### Module not found errors
- Backend: Make sure virtual environment is activated and dependencies are installed: `pip install -r requirements.txt`
- Frontend: Make sure all dependencies are installed: `npm install`
- Delete `node_modules` or `venv` and reinstall if needed

## Development

### Backend API
- API runs on `http://localhost:3001`
- API docs: See README.md for endpoint details

### Frontend
- Hot reload enabled
- Proxy configured to backend API

## Database Location

SQLite database: `backend/data/nextstep.db`

To reset database:
1. Delete `backend/data/nextstep.db`
2. Run `python3 scripts/seed.py` again (with venv activated)

