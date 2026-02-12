# Contributing to Local Talking LLM

First off, thank you for considering contributing to Local Talking LLM! It's people like you that make this project a great tool for privacy-conscious AI enthusiasts.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Guidelines](#code-guidelines)
- [Testing Requirements](#testing-requirements)
- [Submitting Changes](#submitting-changes)
- [Community](#community)

---

## 📜 Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Git
- Basic understanding of LLMs and voice assistants
- Familiarity with pytest for testing

### Development Setup

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/local-talking-llm.git
cd local-talking-llm

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/local-talking-llm.git

# Create a virtual environment
python3.11 -m venv .venv311
source .venv311/bin/activate

# Install dependencies (including dev tools)
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pre-commit install

# Download models for local testing
ollama pull gemma3
ollama pull moondream
ollama pull qwen2.5:0.5b

# Run tests to verify setup
pytest tests/ -v
```

---

## 💻 Development Workflow

### Finding Something to Work On

1. **Check Issues**: Browse [open issues](https://github.com/ORIGINAL_OWNER/local-talking-llm/issues) labeled `good-first-issue` or `help-wanted`
2. **Read Documentation**: Review [CLAUDE.md](CLAUDE.md) and [AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md) for architecture
3. **Check Roadmap**: See [ROADMAP.md](ROADMAP.md) for planned features
4. **Ask Questions**: Comment on issues or start a [Discussion](https://github.com/ORIGINAL_OWNER/local-talking-llm/discussions)

### Creating a Feature Branch

```bash
# Update your fork
git checkout main
git fetch upstream
git merge upstream/main

# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### Making Changes

1. **Read the constraints** in [CLAUDE.md](CLAUDE.md) — especially GPU memory limits
2. **Write tests first** (TDD approach recommended)
3. **Make your changes** following our [Code Guidelines](#code-guidelines)
4. **Run tests** frequently: `pytest tests/ -v`
5. **Lint your code**: `ruff check src/ tests/ app_optimized.py tts.py`

---

## 📐 Code Guidelines

### Architecture Constraints

⚠️ **CRITICAL**: This project is designed for 4GB VRAM GPUs. **Never break these rules:**

1. **GPU Memory Management**
   - Only ONE model in GPU memory at a time
   - Always unload current model before loading a different one
   - Use `ResourceManager` class pattern

2. **Model Sizes** (must fit in 4GB)
   - Gemma3: 3.3GB (text chat)
   - Moondream: 1.7GB (vision)
   - Whisper: CPU only (74MB)
   - Piper TTS: CPU only (60MB)

### Code Style

We use **Ruff** for linting and formatting:

```bash
# Check code style
ruff check src/ tests/ app_optimized.py tts.py

# Auto-fix issues
ruff check --fix src/ tests/

# Format code (if needed)
ruff format src/ tests/
```

**Key style rules:**
- Python 3.11+ features and type hints
- Line length: 120 characters max
- Docstrings for all public functions/classes
- Type hints for function signatures
- Clear variable names (no single letters except loop counters)

### Error Handling

**Always add graceful degradation:**

```python
# GOOD - Component can fail without crashing app
tts_service = None
try:
    tts_service = TextToSpeechService(voice_path=voice_path)
    console.print("[green]TTS ready[/green]")
    log.info("TTS loaded")
except Exception as e:
    log.warning("TTS load failed: %s", e)
    console.print(f"[yellow]TTS unavailable: {e}. Continuing without speech.[/yellow]")

# Later in code
if tts_service:
    try:
        sample_rate, audio = tts_service.synthesize(text)
        play_audio(sample_rate, audio)
    except Exception as e:
        log.error("TTS playback failed: %s", e)
        console.print(f"[yellow]Speech failed: {e}[/yellow]")
```

### Logging

Use structured logging with appropriate levels:

```python
from src.logging_config import get_logger

log = get_logger(__name__)

# DEBUG: Detailed information for diagnosing problems
log.debug("Loading model %s onto GPU", model_name)

# INFO: General informational messages
log.info("User: %s", user_text)
log.info("Intent: %s (confidence=%.2f)", intent, confidence)

# WARNING: Something unexpected but not critical
log.warning("TTS unavailable, continuing without speech")

# ERROR: Serious problem, component failure
log.error("Database init failed: %s", e, exc_info=True)
```

### Configuration

**Never hardcode paths or settings:**

```python
# GOOD - Use config system
voice_path = config.get("tts", {}).get("piper", {}).get("voice_path")
max_history = config.get("chat", {}).get("max_history_messages", 50)

# BAD - Hardcoded
voice_path = "/home/user/.local/share/piper/voice.onnx"
max_history = 50
```

---

## 🧪 Testing Requirements

### Writing Tests

**All new features must include tests.** We use pytest with these conventions:

```python
# tests/test_your_feature.py
"""Tests for your feature."""

def test_feature_basic_case():
    """Test description in docstring."""
    # Arrange
    input_data = "test input"

    # Act
    result = your_function(input_data)

    # Assert
    assert result == expected_output
    assert isinstance(result, str)


def test_feature_edge_case():
    """Test edge cases and error conditions."""
    with pytest.raises(ValueError):
        your_function(invalid_input)
```

### Test Coverage Requirements

- **New features**: 80%+ coverage
- **Bug fixes**: Add test that reproduces the bug
- **Refactoring**: Maintain existing coverage

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_orchestrator.py -v

# Run tests matching pattern
pytest tests/ -k "test_vision" -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Run tests in parallel (faster)
pytest tests/ -n auto
```

### Test Categories

- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test component interactions (DB + vector store)
- **Mock tests**: Use `pytest-mock` for external dependencies (Ollama, audio devices)

---

## 📤 Submitting Changes

### Before Submitting

Checklist before creating a PR:

- [ ] Tests pass: `pytest tests/ -v`
- [ ] Linting passes: `ruff check src/ tests/ app_optimized.py tts.py`
- [ ] GPU memory constraints maintained (if applicable)
- [ ] New features have tests
- [ ] Documentation updated (README, docstrings)
- [ ] CHANGELOG.md updated with your changes
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/) for clear history:

```
type(scope): brief description

Longer explanation if needed.

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding/updating tests
- `refactor`: Code restructuring without behavior change
- `perf`: Performance improvements
- `chore`: Maintenance tasks (deps, build, etc.)

**Examples:**
```
feat(tools): add weather lookup tool

Adds a new tool that fetches current weather using wttr.in API.
Includes retry logic and graceful fallback if service is down.

Closes #45
```

```
fix(vision): prevent GPU OOM when swapping models

Ensure Gemma3 is fully unloaded before loading Moondream.
Adds explicit torch.cuda.empty_cache() call.

Fixes #67
```

### Creating a Pull Request

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a PR** on GitHub from your fork to `upstream/main`

3. **Fill out the PR template** completely:
   - Describe what changed and why
   - Link related issues
   - Add screenshots/videos if UI changes
   - List testing steps

4. **Wait for review** and address feedback:
   - Be responsive to comments
   - Push additional commits to your branch
   - Request re-review when ready

5. **Merge** after approval (maintainers will handle this)

### PR Review Process

- **Automated checks** run first (CI/CD)
- **Maintainer review** typically within 2-3 days
- **Feedback addressed** by you
- **Approval** from at least one maintainer
- **Merge** by maintainer (usually squash merge)

---

## 🤝 Community

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: Questions, ideas, general chat
- **Pull Requests**: Code contributions

### Getting Help

- **Architecture questions**: Read [CLAUDE.md](CLAUDE.md) and [AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md) first
- **Setup issues**: Check [Troubleshooting](README.md#troubleshooting) in README
- **Feature ideas**: Start a [Discussion](https://github.com/ORIGINAL_OWNER/local-talking-llm/discussions)
- **Bugs**: Open an [Issue](https://github.com/ORIGINAL_OWNER/local-talking-llm/issues)

### Recognition

Contributors are recognized in:
- GitHub Contributors page
- CHANGELOG.md for significant features
- README.md acknowledgments (for major contributions)

---

## 📚 Additional Resources

### For AI Assistants Working on This Codebase

If you're an AI assistant (like Claude, GPT, etc.) helping with development:

1. **Read [CLAUDE.md](CLAUDE.md) first** - Critical constraints and patterns
2. **Review [AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md)** - Complete architecture
3. **Follow GPU memory rules** - Only ONE model at a time
4. **Test your changes** - Run `pytest tests/ -v` before committing
5. **Maintain existing patterns** - ResourceManager, logging, error handling

### Project-Specific Docs

- [CLAUDE.md](CLAUDE.md) - AI assistant guidelines
- [AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md) - Architecture deep-dive
- [ROADMAP.md](ROADMAP.md) - Future plans
- [HOW_TO_RUN.md](HOW_TO_RUN.md) - Detailed usage guide

---

## ❓ Questions?

Don't hesitate to ask! We're here to help:

- Comment on an existing issue
- Start a new [Discussion](https://github.com/ORIGINAL_OWNER/local-talking-llm/discussions)
- Reach out to maintainers

---

**Thank you for contributing to Local Talking LLM!** 🎉

Every contribution, no matter how small, helps make this project better for the community.
