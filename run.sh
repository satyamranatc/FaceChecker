#!/bin/bash

# Terminate background processes on exit
trap 'kill $(jobs -p) 2>/dev/null' EXIT

echo "==============================================="
echo "       Aura Class Hub - Startup Console        "
echo "==============================================="

# 1. Start Backend FastAPI Server
echo "[1/2] Launching Backend Server on port 8000..."
cd backend
if [ -d "venv" ]; then
    ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
else
    echo "Creating virtual environment and installing packages..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
fi
cd ..

# 2. Start Frontend Vite Server
echo "[2/2] Launching Frontend Dev Server on port 5173..."
cd frontend
npm run dev &
cd ..

echo "-----------------------------------------------"
echo "Aura Class Hub is initializing!"
echo "-> Classroom Directory & Check-in Feed: http://localhost:5173"
echo "-> API Service Portal: http://localhost:8000"
echo "-----------------------------------------------"
echo "Press Ctrl+C to stop both servers safely."

# Wait for background jobs to run
wait
