# Quick Setup Guide

## Prerequisites
- Node.js 18+ installed
- npm or yarn

## Installation Steps

### 1. Install All Dependencies

```bash
# From project root
npm run install:all
```

Or manually:
```bash
npm install
cd backend && npm install
cd ../frontend && npm install
```

### 2. Seed the Database

```bash
cd backend
npm run seed
```

This creates the SQLite database and populates it with:
- 22 roles
- Learning resources
- 30 questions

### 3. Start the Application

**Terminal 1 - Backend:**
```bash
cd backend
npm run dev
```

Backend will run on `http://localhost:3001`

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Frontend will run on `http://localhost:3000`

### 4. Open in Browser

Navigate to `http://localhost:3000`

## Troubleshooting

### Database not found
- Make sure you ran `npm run seed` in the backend directory
- Check that `backend/data/` directory exists

### Port already in use
- Backend: Change `PORT` in `backend/.env` (default: 3001)
- Frontend: Change `port` in `frontend/vite.config.js` (default: 3000)

### Module not found errors
- Make sure all dependencies are installed: `npm run install:all`
- Delete `node_modules` and reinstall if needed

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
2. Run `npm run seed` again

