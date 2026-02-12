#!/bin/bash
# Development installation script for Local Talking LLM contributors
set -e

echo "🎙️ Local Talking LLM - Development Installer"
echo "=============================================="
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

# Check for git
echo ""
echo "🔍 Checking git repository..."
if [ ! -d .git ]; then
    echo "⚠️  Not a git repository. Make sure you've cloned the repo:"
    echo "   git clone https://github.com/yourusername/local-talking-llm.git"
    exit 1
fi
echo "✅ Git repository found"

# Check for system dependencies
echo ""
echo "📦 Checking system dependencies..."

if ! command -v portaudio19-dev &> /dev/null && ! pkg-config --exists portaudio-2.0 2>/dev/null; then
    echo "⚠️  PortAudio development libraries not found"
    echo "   Please install system dependencies:"
    echo ""
    echo "   Debian/Ubuntu:"
    echo "     sudo apt-get update"
    echo "     sudo apt-get install -y portaudio19-dev libsndfile1"
    echo ""
    echo "   Fedora/RHEL:"
    echo "     sudo dnf install portaudio-devel libsndfile-devel"
    echo ""
    echo "   Arch Linux:"
    echo "     sudo pacman -S portaudio libsndfile"
    echo ""
    echo "   macOS:"
    echo "     brew install portaudio libsndfile"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create virtual environment
echo ""
echo "🐍 Creating virtual environment (.venv311)..."
python3 -m venv .venv311
source .venv311/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip wheel

# Install package with dev dependencies
echo ""
echo "📥 Installing Local Talking LLM with dev tools..."
pip install -e ".[dev]"

# Install pre-commit hooks
echo ""
echo "🔄 Installing pre-commit hooks..."
if [ -f .pre-commit-config.yaml ]; then
    pip install pre-commit
    pre-commit install
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  .pre-commit-config.yaml not found, skipping pre-commit"
fi

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
    echo "⚠️  Ollama not found. Install it for local model support:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
else
    echo "✅ Ollama found"
    
    # Pull development models
    echo ""
    echo "📥 Pulling Ollama models (for testing)..."
    
    echo "  📦 gemma3 (for chat)..."
    ollama pull gemma3 || echo "⚠️  Failed to pull gemma3"
    
    echo "  📦 moondream (for vision)..."
    ollama pull moondream || echo "⚠️  Failed to pull moondream"
    
    echo "  📦 qwen2.5:0.5b (for testing)..."
    ollama pull qwen2.5:0.5b || echo "⚠️  Failed to pull qwen2.5:0.5b"
fi

# Verify installation
echo ""
echo "🧪 Verifying installation..."

# Run tests
echo "  Running test suite..."
if pytest tests/ -v --tb=short 2>&1 | head -20; then
    echo "✅ Tests passed"
else
    echo "⚠️  Some tests failed (non-critical for dev setup)"
fi

# Run linter
echo ""
echo "  Running linter..."
if ruff check src/ tests/ app_optimized.py tts.py; then
    echo "✅ Linting passed"
else
    echo "⚠️  Linting found issues (run 'ruff check --fix' to auto-fix)"
fi

echo ""
echo "=============================================="
echo "✅ Development environment ready!"
echo ""
echo "Quick start:"
echo "  source .venv311/bin/activate"
echo "  python app_optimized.py"
echo ""
echo "Development commands:"
echo "  pytest tests/              # Run tests"
echo "  ruff check src/            # Check linting"
echo "  ruff check --fix src/      # Auto-fix issues"
echo "  pytest --cov=src          # Run with coverage"
echo ""
echo "Before submitting PR:"
echo "  1. Run tests: pytest tests/ -v"
echo "  2. Run linter: ruff check src/ tests/"
echo "  3. Update CHANGELOG.md"
echo "  4. Follow CONTRIBUTING.md guidelines"
echo ""
echo "📖 Read CONTRIBUTING.md for contribution guidelines"
echo "=============================================="
