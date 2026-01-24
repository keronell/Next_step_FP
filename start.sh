#!/bin/bash

# NextStep Career Matcher - One-Click Start Script
# This script sets up and starts the entire application

set -e  # Exit on error

echo "🚀 Starting NextStep Career Matcher..."
echo ""

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"
if ! command_exists python3; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

if ! command_exists node; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

if ! command_exists npm; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18+ is required. Current version: $(node -v)"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites check passed${NC}"
echo ""

# Install dependencies if needed
echo -e "${BLUE}Checking dependencies...${NC}"
if [ ! -d "backend/venv" ]; then
    echo "Creating Python virtual environment..."
    cd backend && python3 -m venv venv && cd ..
fi

if [ ! -d "backend/venv" ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment and install Python dependencies
echo "Installing backend dependencies..."
cd backend
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate
cd ..

if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Generate data files (always regenerate to ensure latest version)
echo -e "${BLUE}Generating data files...${NC}"
cd backend
source venv/bin/activate
python3 scripts/generate_data.py
deactivate
cd ..

echo -e "${GREEN}✓ Data files ready${NC}"
echo ""

# Seed database (delete old database to ensure fresh seed)
echo -e "${BLUE}Seeding database...${NC}"
cd backend
source venv/bin/activate
# Remove old database to ensure fresh seed
if [ -f "data/nextstep.db" ]; then
    rm -f data/nextstep.db
fi
python3 scripts/seed.py
deactivate
cd ..
echo -e "${GREEN}✓ Database seeded${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}

# Trap Ctrl+C and call cleanup
trap cleanup INT TERM

# Start backend server
echo -e "${BLUE}Starting backend server...${NC}"
cd backend
source venv/bin/activate
python3 app.py > ../backend.log 2>&1 &
BACKEND_PID=$!
deactivate
cd ..

# Wait a bit for backend to start
sleep 2

# Start frontend server
echo -e "${BLUE}Starting frontend server...${NC}"
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait a bit for frontend to start
sleep 3

echo ""
echo -e "${GREEN}✅ Application is running!${NC}"
echo ""
echo -e "${BLUE}Backend:${NC}  http://localhost:3001"
echo -e "${BLUE}Frontend:${NC} http://localhost:3000"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for user interrupt
wait
