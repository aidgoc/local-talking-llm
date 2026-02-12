# AI Instructions for Talking LLM Assistant

> **For AI Assistants**: This file contains structured information to help you understand and work with this codebase.

## Quick Project Summary

**Talking LLM Assistant** is a voice-controlled AI assistant with vision capabilities that runs entirely locally.

- **Language**: Python 3.9+
- **Platform**: Linux (Ubuntu/Debian/Fedora/Arch) and macOS
- **Architecture**: Modular with smart GPU memory management
- **Key Constraint**: Only ONE model in GPU at a time (4GB VRAM limit)

## Architecture Overview

```
User Input (Voice) 
    ↓
[Whisper] Speech-to-Text (CPU)
    ↓
Intent Analysis
    ↓
┌─────────────────────────────────┐
│  Vision Request?                │
│  ("what do you see?")           │
└─────────────────────────────────┘
    ↓ YES                     ↓ NO
[Camera] Capture            [Text Chat]
    ↓                           ↓
[Moondream] Vision          [Gemma3] Chat
(GPU - 1.7GB)               (GPU - 3.3GB)
    ↓                           ↓
Unload Vision Model         Keep Text Model
    ↓                           ↓
[Response Text] ←───────────┘
    ↓
[Piper TTS] Text-to-Speech (CPU)
    ↓
Audio Output
```

## Key Components

### 1. ResourceManager Class (Critical!)
**Location**: `app_optimized.py`

**Purpose**: Manages GPU memory by loading/unloading models dynamically

**Key Methods**:
- `unload_current_model()` - Frees GPU memory
- `load_text_model(model_name)` - Loads text chat model (gemma3)
- `load_vision_model(model_name)` - Loads vision model (moondream)
- `get_text_response(text, history)` - Gets chat response
- `get_vision_response(text, image_b64)` - Analyzes image

**Important**: Only one model can be in GPU at a time due to 4GB VRAM constraint.

### 2. capture_image() Function
**Location**: `app_optimized.py`

**Purpose**: Captures image from camera with preview window

**Flow**:
1. Open camera with OpenCV
2. Show live preview with overlay text
3. Wait for SPACE (capture), ESC (cancel), or 5s timeout
4. Resize image to 512x384 for efficiency
5. Convert to base64 JPEG

### 3. process_interaction() Function
**Location**: `app_optimized.py`

**Purpose**: Main processing pipeline for each user interaction

**Steps**:
1. Transcribe audio (CPU)
2. Check if vision keywords present
3. Capture image if vision request
4. Get response from appropriate model
5. Unload vision model (if not keep-loaded)
6. Convert to speech (CPU)
7. Play audio

### 4. TextToSpeechService Class
**Location**: `tts.py`

**Purpose**: Text-to-speech using Piper

**Key Methods**:
- `synthesize(text)` - Converts text to audio (returns sample_rate, audio_array)
- `long_form_synthesize(text)` - Wrapper for longer text
- `save_voice_sample(text, output_path)` - Saves to file

## File Structure

```
local-talking-llm/
├── app_optimized.py         # Main application entry
├── tts.py                   # Text-to-speech module
├── src/                     # Core modules
│   ├── database.py          # SQLite persistence + semantic search
│   ├── vector_store.py      # zvec semantic embeddings (CPU)
│   ├── tools.py             # Tool system for LLM
│   ├── orchestrator.py      # Intent routing
│   └── ...                  # Other modules
├── config/
│   └── default.yaml         # Default configuration
├── tests/                   # Test suite
└── run_optimized.sh         # Launcher script
```

## Configuration

**Location**: `config/default.yaml`

**Key Settings**:
```yaml
text_model: gemma3              # Text chat model (3.3GB)
vision_model: moondream         # Vision model (1.7GB)
whisper_model: base.en          # Speech recognition (74MB)
tts_voice: en_US-lessac-medium  # Voice model (60MB)

performance:
  use_gpu: true
  keep_vision_loaded: false     # Keep vision model in GPU (faster but uses VRAM)
  silence_timeout: 1.5

camera:
  preview_width: 640
  preview_height: 480
  capture_width: 512           # Optimized for MX130
  capture_height: 384
  quality: 85
  auto_capture_timeout: 5
```

## Common Tasks for AI Assistants

### Adding a New Model
1. Add model name to `config/default.yaml`
2. Update `ResourceManager` to support the model
3. Add model download instructions
4. Update documentation

### Adding a New Feature
1. Identify where in the pipeline it fits
2. Check GPU memory impact (critical!)
3. Add configuration option to `default.yaml`
4. Update `app_optimized.py` with clear comments
5. Test with `--vision` flag if applicable

### Fixing a Bug
1. Check logs at startup for errors
2. Verify Ollama is running: `curl http://localhost:11434/api/tags`
3. Check GPU memory: `nvidia-smi` or check console output
4. Common issues:
   - Camera permissions (macOS)
   - Out of GPU memory (close other apps)
   - Ollama not started

### Modifying UI
- Uses Rich library for terminal UI
- Look for `console.print()` calls
- Colors: `[green]`, `[red]`, `[yellow]`, `[blue]`, `[cyan]`
- Panels: `Panel.fit()` for boxed sections
- Status: `console.status()` with spinner

## Important Constraints

1. **GPU Memory**: 4GB limit - only one model at a time
2. **Whisper runs on CPU**: To save GPU VRAM
3. **TTS runs on CPU**: Uses ONNX runtime
4. **Models**:
   - Gemma3: 3.3GB (text chat)
   - Moondream: 1.7GB (vision)
   - Both can't be loaded simultaneously
5. **Camera**: Requires manual capture (SPACE/ESC/timeout)

## Code Style Guide

- **Type hints**: Use Python 3.9+ syntax (`str | None`)
- **Docstrings**: Google style with Args/Returns
- **Comments**: Explain WHY, not WHAT
- **Functions**: Single responsibility, clear names
- **Classes**: ResourceManager pattern for GPU resources
- **Error handling**: Graceful degradation, user-friendly messages

## Testing Commands

```bash
# Test basic functionality
talking-llm

# Test with vision
talking-llm --vision

# Test specific model
talking-llm --model gemma3 --whisper-model base.en

# Check Ollama
curl http://localhost:11434/api/tags

# Check GPU
nvidia-smi
```

## Dependencies to Know

- **Whisper**: OpenAI speech recognition
- **Piper**: Local TTS (lightweight)
- **Ollama**: Local LLM serving
- **LangChain**: AI orchestration
- **OpenCV**: Camera access
- **Rich**: Terminal UI

## New Features Reference (Added in v1.1.0)

### Voice Activity Detection (VAD)
**Location**: `src/vad.py` and `app_optimized.py:record_audio_with_vad()`
**Purpose**: Automatically stop recording when user stops speaking
**Usage**: `--use-vad --silence-timeout 1.5 --vad-aggressiveness 2`
**Dependencies**: `webrtcvad-wheels`
**Key Functions**: `VoiceActivityDetector`, `AudioFrameBuffer`, `create_default_vad()`
**Important**: Falls back gracefully if VAD not installed

### Wake Word Detection
**Location**: `src/wake_word.py`
**Purpose**: Continuous background listening for "Hey Assistant"
**Usage**: `--wake-word --wake-phrases "hey assistant" --wake-threshold 0.7`
**Features**: 
- Fuzzy keyword matching with adjustable threshold
- VAD integration for power efficiency
- Continuous background listening
- Falls back to manual mode if fails

### Performance Monitoring
**Location**: `src/perf_monitor.py`
**Purpose**: Track timing metrics and resource usage
**Usage**: `--perf` flag
**Features**:
- Timing for transcription, LLM, vision, TTS
- GPU memory tracking
- Session summary report on exit
- Decorator (`@timed("component")`) for easy integration

## When Modifying Code

**ALWAYS**:
1. Check GPU memory impact
2. Maintain the ResourceManager pattern
3. Add error handling for missing hardware
4. Update configuration options if needed
5. Test with both text and vision modes
6. Test with new features (--use-vad, --wake-word, --perf)

**NEVER**:
1. Load multiple models simultaneously without checking VRAM
2. Remove the unload_current_model() calls
3. Hardcode paths - use CONFIG_DIR and APP_DIR
4. Break the modular structure
5. Break VAD or wake word fallback mechanisms

## External APIs

**Ollama API** (used for vision):
```python
POST http://localhost:11434/api/chat
{
    "model": "moondream",
    "messages": [{
        "role": "user",
        "content": "What do you see?",
        "images": [base64_encoded_image]
    }],
    "stream": false
}
```

## Performance Expectations

| Hardware | Text Chat | Vision | TTS |
|----------|-----------|--------|-----|
| RTX 3060 (12GB) | 2s | 3s | 1s |
| GTX 1650 (4GB) | 3s | 5s | 1s |
| MX130 (4GB) | 4s | 8s | 1s |
| M1 Mac (8GB) | 3s | 4s | 1s |
| CPU Only | 8s | 15s | 1s |

Vision is slower due to model switching (gemma3 → moondream → gemma3).

## License

MIT License - See LICENSE file

---

**Last Updated**: 2024-02-11
**For AI Assistants**: When modifying code, always verify GPU memory management remains intact.
