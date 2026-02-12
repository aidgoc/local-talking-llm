#!/bin/bash

# Run LTL with fixed TTS module
# This script ensures scipy is installed for resampling

cd "$(dirname "$0")"
source .venv311/bin/activate

# Make sure scipy is installed
pip install -q scipy

# Run the application
python app_optimized.py "$@"