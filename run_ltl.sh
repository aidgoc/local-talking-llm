#!/bin/bash
# LTL Launcher Script
# This script provides a simple way to run LTL components

cd "$(dirname "$0")"

echo "🎙️ LTL Launcher"
echo "==============="
echo ""

# Check if we're in the right directory
if [ ! -f "app_optimized.py" ]; then
    echo "❌ Error: app_optimized.py not found. Please run from the LTL directory."
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found."
    exit 1
fi

echo "Available options:"
echo "1. Launch TUI (recommended) - ltl"
echo "2. Voice Assistant - python3 app_optimized.py"
echo "3. Text Chat - python3 -m ltl chat"
echo "4. Setup - python3 -m ltl setup"
echo ""

read -p "Choose option (1-4) or press Enter for TUI: " choice

case $choice in
    1|"")
        echo "Launching TUI..."
        python3 -m ltl
        ;;
    2)
        echo "Launching Voice Assistant..."
        echo "Note: May require additional dependencies"
        python3 app_optimized.py
        ;;
    3)
        echo "Launching Text Chat..."
        python3 -m ltl chat
        ;;
    4)
        echo "Launching Setup..."
        python3 -m ltl setup
        ;;
    *)
        echo "Invalid choice. Launching TUI..."
        python3 -m ltl
        ;;
esac