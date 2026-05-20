#!/bin/bash
# Script to run the meeting analyzer app

# Set the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$PROJECT_DIR"

# Activate venv if it exists
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
elif [ -f ".venv/Scripts/activate" ]; then
    source ".venv/Scripts/activate"
fi

# Run the app
python "backend/main.py"