#!/bin/bash
# Installation script for Local Talking LLM
set -e

echo "🎙️ Local Talking LLM - Production Installer"
echo "============================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
REQUIRED_VERSION="3.11"

if [ -z "$PYTHON_VERSION" ]; then
    echo "❌ Python 3 not found. Please install Python 3.11 or higher."
    exit 1
fi

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $PYTHON_VERSION found, but $REQUIRED_VERSION or higher is required."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

# Check for system dependencies
echo ""
echo "📦 Checking system dependencies..."

if ! command -v portaudio19-dev &> /dev/null && ! pkg-config --exists portaudio-2.0 2>/dev/null; then
    echo "⚠️  PortAudio development libraries not found"
    echo "   Please install: sudo apt-get install portaudio19-dev libsndfile1 (Debian/Ubuntu)"
    echo "   Or: sudo pacman -S portaudio (Arch)"
    echo "   Or: brew install portaudio (macOS)"
fi

# Create virtual environment
echo ""
echo "🐍 Creating virtual environment..."
python3 -m venv .venv311
source .venv311/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install package
echo ""
echo "📥 Installing Local Talking LLM..."
pip install -e .

# Install optional dev dependencies
echo ""
echo "🛠️  Installing development tools..."
pip install ruff pytest pytest-mock pytest-cov

# Create necessary directories
echo ""
echo "📁 Creating data directories..."
mkdir -p ~/.local/share/talking-llm/logs
mkdir -p ~/.local/share/talking-llm/models
mkdir -p ~/.config/talking-llm

# Copy default config if it doesn't exist
if [ ! -f ~/.config/talking-llm/config.yaml ]; then
    echo "⚙️  Creating default configuration..."
    cp config/default.yaml ~/.config/talking-llm/config.yaml
fi

# Download Piper voice if not exists
PIPER_VOICE="$HOME/.local/share/piper/en_US-lessac-medium.onnx"
if [ ! -f "$PIPER_VOICE" ]; then
    echo ""
    echo "🔊 Downloading Piper TTS voice model..."
    mkdir -p ~/.local/share/piper
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx" -o "$PIPER_VOICE"
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" -o "$PIPER_VOICE.json"
    echo "✅ Piper voice downloaded"
else
    echo "✅ Piper voice already exists"
fi

# Check for Ollama
echo ""
echo "🦙 Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama not found. Please install it:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    echo "   After installing, run: ollama pull gemma3"
else
    echo "✅ Ollama found"
    
    # Check if models are pulled
    echo ""
    echo "📥 Checking Ollama models..."
    
    if ! ollama list | grep -q "gemma3"; then
        echo "📦 Pulling gemma3 model (this may take a while)..."
        ollama pull gemma3
    else
        echo "✅ gemma3 model available"
    fi
    
    if ! ollama list | grep -q "moondream"; then
        echo "📦 Pulling moondream model (this may take a while)..."
        ollama pull moondream
    else
        echo "✅ moondream model available"
    fi
fi

echo ""
echo "============================================"
echo "✅ Installation complete!"
echo ""
echo "To get started:"
echo "  1. Activate the environment: source .venv311/bin/activate"
echo "  2. Run the assistant: python app_optimized.py"
echo "  3. Or use the launcher: ./run_optimized.sh"
echo ""
echo "For more options:"
echo "  python app_optimized.py --help"
echo ""
echo "📖 Documentation: README.md"
echo "🐛 Issues: https://github.com/yourusername/local-talking-llm/issues"
echo "============================================"
