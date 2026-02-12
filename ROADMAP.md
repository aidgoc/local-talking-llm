# Development Roadmap

> Machine-readable roadmap for Talking LLM Assistant
> Format: [ ] = Not started, [~] = In progress, [x] = Complete

## High Priority Features

### Core Functionality
- [x] Voice recognition with Whisper
- [x] Text chat with Gemma3
- [x] Vision with Moondream
- [x] Text-to-speech with Piper
- [x] Smart GPU memory management
- [x] Camera preview with capture
- [x] Configuration file support
- [x] Wake word detection ("Hey Assistant")
- [x] Continuous listening mode
- [x] Voice Activity Detection (VAD) for auto-stop recording
- [x] Performance monitoring and metrics
- [ ] Conversation history persistence

### Performance Optimization
- [x] Optimized for 4GB VRAM
- [x] CPU-only Whisper to save GPU
- [x] Dynamic model loading/unloading
- [ ] Faster vision mode (keep model loaded option)
- [ ] Batch processing for TTS
- [ ] Async model loading
- [ ] Model quantization support

### Platform Support
- [x] Linux (Ubuntu/Debian/Fedora/Arch)
- [x] macOS
- [ ] Windows support
- [ ] Raspberry Pi / ARM support
- [ ] Docker containerization

## Medium Priority Features

### User Experience
- [ ] GUI version (PyQt/Tkinter)
- [ ] Web interface
- [ ] Mobile app companion
- [ ] Multiple voice options
- [ ] Voice emotion detection
- [ ] Custom wake words
- [ ] Keyboard shortcuts
- [ ] System tray integration

### AI Capabilities
- [ ] Multi-language support
- [ ] Better vision (video streams)
- [ ] OCR improvements
- [ ] Object detection
- [ ] Face recognition (opt-in)
- [ ] Custom model support
- [ ] Fine-tuning interface

### Integration
- [ ] Plugin system
- [ ] Home Assistant integration
- [ ] MQTT support
- [ ] API server mode
- [ ] Webhook support
- [ ] Calendar integration
- [ ] Email integration

## Low Priority Features

### Advanced Features
- [ ] Voice cloning
- [ ] Multi-user profiles
- [ ] Cloud sync option
- [ ] Remote access
- [ ] Distributed processing
- [ ] Model marketplace

### Developer Tools
- [ ] Comprehensive test suite
- [x] Benchmarking tools (--perf flag)
- [x] Debug mode (--perf with timing metrics)
- [x] Performance profiler (perf_monitor.py)
- [ ] Plugin SDK
- [ ] Documentation generator

## Bug Fixes & Improvements

### Known Issues
- [ ] Camera permissions on macOS (requires manual grant)
- [ ] Wayland display issues on Linux
- [ ] Bluetooth audio latency
- [ ] Vision mode slow (8-10s due to model switching)

### Code Quality
- [ ] Unit tests for all modules
- [ ] Integration tests
- [ ] Type checking (mypy)
- [ ] Linting (ruff/black)
- [ ] Documentation coverage
- [ ] Error handling improvements

## Documentation

- [x] User README
- [x] Quickstart guide
- [x] AI instructions
- [ ] API documentation
- [ ] Developer guide
- [ ] Contributing guide
- [ ] Troubleshooting guide
- [ ] Video tutorials
- [ ] Example scripts

## Distribution

- [x] Linux installer
- [x] macOS installer
- [ ] Windows installer
- [ ] Homebrew formula
- [ ] APT repository
- [ ] Snap package
- [ ] Flatpak package
- [ ] Docker image
- [ ] GitHub releases

---

## Current Status

**Version**: 1.1.0  
**Status**: ✅ Production Ready  
**Next Milestone**: v1.2.0 - GUI Interface + Plugin System  
**Priority**: Medium on GUI development

## How to Contribute

1. Pick an unchecked item from above
2. Create a branch: `git checkout -b feature/wake-word`
3. Implement following AI_INSTRUCTIONS.md
4. Test with `python app_optimized.py --vision`
5. Update documentation
6. Submit PR

## Resource Requirements for New Features

When adding features, ensure they fit within:
- **GPU**: 4GB VRAM (only one model at a time)
- **RAM**: 8GB minimum, 16GB recommended
- **CPU**: Can offload from GPU for non-realtime tasks
- **Disk**: Keep under 20GB total

## Model Sizes Reference

```
Gemma3:        3.3 GB  (text chat)
Moondream:     1.7 GB  (vision)
Llama3.2:      2.0 GB  (alternative text)
Whisper tiny:  39 MB   (fastest STT)
Whisper base:  74 MB   (balanced STT)
Whisper small: 461 MB  (best STT)
Piper voice:   60 MB   (TTS)
```

---

**Last Updated**: 2024-02-11  
**Next Review**: When v1.1.0 is released
