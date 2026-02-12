# Talking LLM Assistant - opencode Context

## Quick Reference

**Project Type**: Python Voice AI Assistant  
**Main Language**: Python 3.9+  
**Key Dependencies**: Ollama, Whisper, Piper TTS, OpenCV, LangChain, Rich  
**Platform**: Linux, macOS  
**License**: MIT

## Critical Information

### GPU Memory Constraint (CRITICAL)
- **Limit**: 4GB VRAM maximum
- **Rule**: Only ONE model in GPU at a time
- **Pattern**: Always unload before loading different model

### Model Sizes
```
Gemma3:      3.3 GB (text chat)
Moondream:   1.7 GB (vision)
Whisper:     74 MB  (CPU only)
Piper TTS:   60 MB  (CPU only)
```

## File Map

| File | Purpose | Lines |
|------|---------|-------|
| `src/main.py` | Main application | 500+ |
| `src/tts.py` | Text-to-speech | 108 |
| `config/default.yaml` | Configuration | 53 |
| `install.sh` | Installation script | 476 |

## Key Classes

### ResourceManager (src/main.py:89-255)
- **Purpose**: Manages GPU memory
- **Critical**: Only one model loaded at a time
- **Methods**:
  - `unload_current_model()` - Free GPU
  - `load_text_model()` - Load gemma3
  - `load_vision_model()` - Load moondream
  - `get_text_response()` - Chat
  - `get_vision_response()` - Vision

## Common Patterns

### GPU Memory Management
```python
# CORRECT pattern
resource_mgr.load_text_model()
# ... use text model ...
resource_mgr.unload_current_model()  # FREE GPU FIRST
resource_mgr.load_vision_model()

# WRONG - will OOM
resource_mgr.load_text_model()
resource_mgr.load_vision_model()  # ❌ GPU overflow!
```

### Configuration Loading
```python
def load_config():
    default_config = {...}
    if os.path.exists(CONFIG_FILE):
        config = yaml.safe_load(f)
        # Merge with defaults
        return {**default_config, **config}
    return default_config
```

## Testing Commands

```bash
# Basic test
talking-llm

# With vision
talking-llm --vision

# Check Ollama
curl http://localhost:11434/api/tags

# Check GPU memory
python -c "import torch; print(f'GPU: {torch.cuda.memory_allocated()/1e9:.2f}GB')"
```

## Documentation Files

- `AI_INSTRUCTIONS.md` - Comprehensive architecture
- `CLAUDE.md` - Claude-specific instructions
- `ROADMAP.md` - Development roadmap with checkboxes
- `PROJECT_CONTEXT.md` - Original project context
- `README.md` - User documentation

## When Modifying Code

### ALWAYS:
- [ ] Check GPU memory impact
- [ ] Maintain ResourceManager pattern
- [ ] Add error handling
- [ ] Update configuration if needed
- [ ] Test with `--vision` flag
- [ ] Update both app_optimized.py and dist/.../src/main.py

### NEVER:
- [ ] Load multiple models without unloading
- [ ] Hardcode paths (use APP_DIR, CONFIG_DIR)
- [ ] Break GPU memory management
- [ ] Remove unload_current_model() calls

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No microphone" | Check permissions, `arecord -l` |
| "Camera failed" | Check permissions, `ffplay /dev/video0` |
| "Out of memory" | Close other GPU apps, check `nvidia-smi` |
| "Ollama not found" | Run `ollama serve` or install |
| "Slow vision" | Normal - 8-10s due to model switching |

## External Dependencies

- **Ollama**: localhost:11434 (must be running)
- **Whisper**: ~/.cache/whisper/ (auto-downloaded)
- **Piper**: ~/.local/share/piper/ (installed by script)
- **Models**: Downloaded via `ollama pull`

## License

MIT License
