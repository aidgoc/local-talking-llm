#!/bin/bash
# Personal Assistant - Orchestrated Model Routing
# CPU + 4GB MX-130 GPU | One model at a time

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate the first available venv
if [ -d ".venv311" ]; then
    source .venv311/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "No virtual environment found. Create one first."
    exit 1
fi

python app_optimized.py \
    --whisper-model base.en \
    "$@"
