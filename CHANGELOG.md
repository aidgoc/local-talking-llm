# Changelog

All notable changes to Local Talking LLM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-02-12

### 🎉 Production-Ready Release

This release transforms the project from a prototype into a production-ready application suitable for deployment as a systemd service or long-running daemon.

### Added

#### Core Reliability
- **Structured Logging** (`src/logging_config.py`)
  - Rotating file handler (5MB x 3 backups) at `~/.local/share/talking-llm/logs/assistant.log`
  - Console output with configurable log levels (DEBUG, INFO, WARNING, ERROR)
  - Persistent logs survive crashes for debugging

- **Startup Health Checks** (`src/health.py`)
  - Validates Ollama connectivity and model availability
  - Checks audio input devices
  - Verifies Piper voice model existence
  - Fails fast with clear error messages on critical issues
  - Warnings for non-critical failures (TTS, etc.)

- **Graceful Degradation**
  - TTS failure → app continues without speech output
  - Search failure → falls back to text-only mode
  - Database failure → app continues without persistence
  - Component init failures wrapped in try/except

- **Bounded Chat History** (`src/bounded_history.py`)
  - Prevents unbounded memory growth in long sessions
  - Configurable max messages (default: 50)
  - Prunes oldest message pairs to maintain conversation coherence

- **Retry Logic** (`src/retry.py`)
  - Exponential backoff retry decorator
  - Applied to Ollama and OpenRouter HTTP calls
  - Handles transient network failures gracefully

- **Signal Handling**
  - Clean shutdown on SIGTERM/SIGINT
  - Properly frees GPU memory via `ResourceManager.unload_all()`
  - Closes database connections
  - Closes HTTP clients (OpenRouter)

- **Exception Safety**
  - Main loop wrapped in try/except
  - Interaction errors logged with full traceback
  - Session continues after individual interaction failures

#### Configuration & Validation
- **Config Validation** (`src/config_loader.py`)
  - Validates backend choice (`ollama`, `openrouter`, `auto`)
  - Validates Whisper model size
  - Checks for required API keys when using cloud backends
  - Early exit on invalid configuration with helpful error messages

#### Testing & Quality
- **Comprehensive Test Suite** (75 tests, 99% pass rate)
  - `tests/test_database.py` - Database operations + vector store integration
  - `tests/test_orchestrator.py` - Intent classification (20 tests)
  - `tests/test_tools.py` - Tool system fast-path + handlers
  - `tests/test_bounded_history.py` - History pruning behavior
  - `tests/test_health.py` - Health check mocking
  - `tests/test_config_loader.py` - Config loading + validation

- **CI/CD Pipeline** (`.github/workflows/ci.yml`)
  - Automated linting with ruff on every PR/push
  - Automated test execution
  - Python 3.11 compatibility validation

- **Code Quality**
  - Ruff linter configuration (`ruff.toml`)
  - All created/modified files pass lint checks
  - Consistent code style across project

#### Deployment
- **systemd Service File** (`contrib/talking-llm.service`)
  - Run as system service with auto-restart
  - Proper dependency management (`After=ollama.service`)
  - Hardening with `NoNewPrivileges`, `ProtectSystem`

### Changed

- **Improved Error Messages**
  - User-friendly messages for missing dependencies
  - Hints for common issues (camera permissions, Ollama status)
  - Structured logging provides detailed context in logs

- **Robust Component Initialization**
  - Each component (DB, TTS, search, tools) wrapped in try/except
  - App continues with degraded functionality rather than crashing
  - Clear console output shows which components initialized successfully

- **Portability** (`run_optimized.sh`)
  - Uses `$SCRIPT_DIR` instead of hardcoded paths
  - Works from any directory

- **Dependencies** (`pyproject.toml`, `requirements.txt`)
  - Added `pytest>=8.0.0`, `pytest-mock>=3.12.0`, `ruff>=0.9.0` to dev deps
  - Cleaned up requirements.txt (removed 80+ stale packages)
  - Synced with actual project dependencies

### Fixed

- **Memory Leak** - Unbounded chat history now limited to 50 messages (configurable)
- **Crash on Missing TTS** - App now continues without speech output
- **Crash on Ollama Down** - Health check catches this at startup
- **Unhandled Exceptions** - Main loop catches and logs errors, continues session
- **No Cleanup on Exit** - Signal handlers now properly free resources

### Documentation

- **Updated README.md** - Comprehensive production-ready documentation
- **Added CHANGELOG.md** - This file
- All production features documented with examples

---

## [1.0.0] - 2024-XX-XX

### Initial Release

- Voice interaction with Whisper STT
- Text chat with Gemma3 LLM
- Vision analysis with Moondream
- DuckDuckGo web search
- Piper TTS
- Memory system with semantic search
- Task management
- Dual backend support (Ollama/OpenRouter)

---

## [Unreleased]

### Planned for v2.1.0

- [ ] Docker support with docker-compose
- [ ] Example configuration files
- [ ] CONTRIBUTING.md guidelines
- [ ] Wake word detection improvements
- [ ] Multi-language support

