# CLAUDE.md - Instructions for Claude Code / opencode

This file contains specific instructions for Claude-based AI assistants working on this project.

## Quick Start for AI Assistants

When a user asks you to work on this project, follow these steps:

1. **Read this file first** (CLAUDE.md) - You're here!
2. **Read AI_INSTRUCTIONS.md** - Comprehensive architecture guide
3. **Check the main files** in this order:
   - `app_optimized.py` - Main application
   - `src/` - Core modules (database, tools, orchestrator, etc.)
   - `config/default.yaml` - Configuration
   - `tts.py` - TTS module

## Critical Constraints (NEVER Break These)

### 1. GPU Memory Management
- **VRAM Limit**: 4GB maximum
- **Rule**: Only ONE model in GPU at a time
- **Pattern**: Use ResourceManager class always
- **Never**: Load multiple models simultaneously

### 2. Model Sizes
```
Gemma3:      3.3 GB  (text chat)
Moondream:   1.7 GB  (vision)
Whisper:     74 MB   (CPU only)
Piper TTS:   60 MB   (CPU only)
```

### 3. ResourceManager Usage
```python
# ALWAYS use this pattern:
resource_mgr.load_text_model()      # Loads gemma3
# ... use text model ...
resource_mgr.unload_current_model() # Free GPU before loading vision
resource_mgr.load_vision_model()    # Loads moondream
# ... use vision model ...
resource_mgr.unload_current_model() # Free GPU after vision
```

## Common User Requests

### "Add feature X"
1. Check if it fits in the pipeline (see AI_INSTRUCTIONS.md flowchart)
2. Verify GPU memory impact
3. Add to appropriate section in app_optimized.py or src/
4. Update config/default.yaml if needed
5. Add error handling for missing hardware

### "Fix bug Y"
1. Check Ollama status: `curl http://localhost:11434/api/tags`
2. Check GPU memory: Look for "GPU:" line in console output
3. Check camera permissions (especially on macOS)
4. Review ResourceManager unload/load sequence

### "Make it faster"
1. Check if vision model is being unloaded unnecessarily
2. Consider `--keep-vision-loaded` flag
3. Check Whisper model size (tiny.en is fastest)
4. Verify GPU is being used: `torch.cuda.is_available()`

### "Add new model"
1. Check model size (must be <4GB alone)
2. Add to config/default.yaml
3. Update ResourceManager class
4. Add download to install.sh
5. Test with both text and vision modes

## Code Patterns to Follow

### Error Handling
```python
# Always provide user-friendly error messages
if not cap.isOpened():
    console.print("[red]❌ Could not open camera!")
    console.print("[yellow]Hint: Check camera permissions in System Settings")
    return None
```

### GPU Memory Check
```python
# Always check GPU availability
def show_resource_usage():
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.memory_allocated() / 1e9
        gpu_total = torch.cuda.get_device_properties(0).total_memory / 1e9
        console.print(f"[dim]GPU: {gpu_mem:.1f}GB / {gpu_total:.1f}GB[/dim]")
```

### Configuration Loading
```python
# Always merge with defaults
def load_config():
    default_config = { ... }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            # Merge with defaults
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    return default_config
```

## File Modification Checklist

When modifying any file, ensure:

- [ ] GPU memory management maintained
- [ ] Error handling for missing hardware
- [ ] User-friendly error messages
- [ ] Configuration options updated if needed
- [ ] Comments explain WHY not WHAT
- [ ] Type hints used (Python 3.9+ style)
- [ ] Test with `--vision` flag if applicable

## Testing Commands

After making changes, verify with:

```bash
# 1. Test basic functionality
. .venv311/bin/activate
python app_optimized.py

# 2. Test with vision
python app_optimized.py --vision

# 3. Check Ollama
curl http://localhost:11434/api/tags

# 4. Check GPU memory
python -c "import torch; print(f'GPU: {torch.cuda.memory_allocated()/1e9:.2f}GB')"
```

## Project Structure Reminder

```
local-talking-llm/
├── app_optimized.py              # ⭐ MAIN APPLICATION
├── tts.py                        # TTS module
├── run_optimized.sh              # ⭐ RECOMMENDED LAUNCHER
├── src/                          # Core modules
│   ├── database.py              # SQLite persistence + semantic search
│   ├── vector_store.py          # zvec semantic embeddings (CPU)
│   ├── tools.py                 # Tool system for LLM
│   ├── orchestrator.py          # Intent routing
│   ├── openrouter.py            # OpenRouter backend
│   ├── web_search.py            # Web search
│   ├── vad.py                   # Voice activity detection
│   ├── wake_word.py             # Wake word detection
│   ├── perf_monitor.py          # Performance monitoring
│   ├── piper_tts.py             # Piper TTS wrapper
│   ├── connectivity.py          # Network checks
│   ├── location.py              # Geolocation
│   └── config_loader.py         # Config loading
├── config/default.yaml           # Configuration
├── tests/                        # Test suite
└── AI_INSTRUCTIONS.md           # Architecture guide
```

## Key External Dependencies

- **Ollama**: Must be running on localhost:11434
- **Whisper**: Downloads on first use to ~/.cache/whisper/
- **Piper**: Voice model at ~/.local/share/piper/
- **Models**: Pulled via `ollama pull gemma3` and `ollama pull moondream`

## Response Patterns

When users ask questions:

**"How do I...?"**
- Check AI_INSTRUCTIONS.md for architecture
- Check main.py for implementation details
- Provide specific line numbers

**"Why isn't X working?"**
- Check Ollama status
- Check GPU memory
- Check permissions (camera/mic)
- Check model downloads

**"Can you add X?"**
- Assess GPU impact first
- Suggest implementation approach
- Point to relevant files
- Remind about testing

## Documentation Files

- **README.md**: User-facing documentation
- **AI_INSTRUCTIONS.md**: Detailed architecture (read this!)
- **CLAUDE.md**: This file - Claude-specific instructions

## Important Notes

1. **Always check GPU memory constraints** before suggesting changes
2. **Test with --vision flag** when modifying vision-related code
3. **Maintain ResourceManager pattern** - it's critical for 4GB VRAM
4. **Update app_optimized.py and relevant src/ modules** when making changes
5. **Use Rich for UI** - console.print(), Panel, Status
6. **Follow existing code style** - type hints, docstrings, comments

## License

MIT License

---

**For Claude/opencode**: Always prioritize GPU memory management. Never break the "one model at a time" rule.
