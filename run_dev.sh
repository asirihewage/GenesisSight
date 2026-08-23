#!/bin/bash
# GenesisSight - Local AI CCTV Analyzer
# Quick script to run the application in development mode

set -e

# Change to project root
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== GenesisSight Dev Environment ==="
echo ""

# Check if Python environment is set up
if [ ! -d "backend/.venv" ] && [ ! -d "backend/venv" ]; then
    echo "WARNING: No Python virtual environment found."
    echo "You may need to install dependencies first."
    echo "Run: pip install -r backend/requirements.txt"
    echo ""
fi

# Activate venv if it exists
if [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate
elif [ -d "backend/venv" ]; then
    source backend/venv/bin/activate
fi

# Install frontend deps if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install --no-audit --no-fund
    cd ..
fi

# Start the application in dev mode
echo "Starting GenesisSight in development mode..."
echo "  Backend API: http://localhost:8000"
echo "  Frontend:    http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python start.py --no-browser "$@"