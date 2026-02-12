# Troubleshooting Guide for AI Assistants

## Quick Diagnosis Checklist

When something isn't working, check these in order:

1. ✅ Ollama is running: `curl http://localhost:11434/api/tags`
2. ✅ Models are downloaded: `ollama list`
3. ✅ GPU has memory: Check console output or `nvidia-smi`
4. ✅ Python environment is active: `which python`
5. ✅ Camera permissions granted (macOS): System Preferences

## Common Issues and Solutions

### Issue: "No module named X"
**Cause**: Python environment not activated or dependencies not installed  
**Solution**:
```bash
source ~/.local/share/talking-llm/venv/bin/activate
pip install -r requirements.txt
```

### Issue: "Could not open camera"
**Cause**: Camera permissions or camera in use  
**Solutions**:
- **Linux**: `sudo usermod -a -G video $USER` then logout/login
- **macOS**: Grant permissions in System Preferences → Security & Privacy → Camera
- **Check if camera works**: `ffplay /dev/video0` (Linux) or Photo Booth (macOS)

### Issue: "No microphone detected"
**Cause**: Microphone permissions or wrong device  
**Solutions**:
- **List devices**: `arecord -l` (Linux), `system_profiler SPAudioDataType` (macOS)
- **Test mic**: `arecord test.wav -d 5 && aplay test.wav`
- **Check permissions**: System Preferences → Security & Privacy → Microphone (macOS)

### Issue: "Out of GPU memory" / "CUDA out of memory"
**Cause**: Trying to load multiple models or other app using GPU  
**Solutions**:
1. Close other applications using GPU
2. Check what's using GPU: `nvidia-smi`
3. Use smaller models:
   ```bash
   talking-llm --model gemma3 --whisper-model tiny.en
   ```
4. The app should automatically manage memory - check ResourceManager is working

### Issue: "Ollama connection refused"
**Cause**: Ollama service not running  
**Solutions**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Or on Linux with systemd
sudo systemctl start ollama
sudo systemctl enable ollama
```

### Issue: "Model not found"
**Cause**: Models not downloaded  
**Solution**:
```bash
ollama pull gemma3
ollama pull moondream
ollama list  # Verify they're there
```

### Issue: "Slow vision mode" (8-10 seconds)
**Cause**: Normal - model switching takes time  
**Solutions**:
- This is expected behavior on 4GB GPUs
- The app unloads gemma3, loads moondream, then reloads gemma3
- To speed up: Use `--keep-vision-loaded` (uses more VRAM)
- Alternative: Get GPU with more VRAM (8GB+ allows both models)

### Issue: "Whisper transcription is poor"
**Cause**: Model too small or microphone quality  
**Solutions**:
- Use larger Whisper model: `--whisper-model small.en` (uses more RAM)
- Check microphone quality
- Speak clearly and at normal volume
- Reduce background noise

### Issue: "TTS not working"
**Cause**: Piper voice model not downloaded or sound system issue  
**Solutions**:
1. Check voice model exists:
   ```bash
   ls ~/.local/share/talking-llm/piper-voices/
   ```
2. Re-download if missing:
   ```bash
   cd ~/.local/share/talking-llm/piper-voices/
   curl -L -o en_US-lessac-medium.onnx \
       "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
   ```
3. Check audio system: `aplay test.wav`

### Issue: "App crashes on startup"
**Cause**: Missing dependencies or wrong Python version  
**Solutions**:
1. Check Python version: `python3 --version` (need 3.9+)
2. Reinstall in fresh environment:
   ```bash
   rm -rf ~/.local/share/talking-llm/venv
   talking-llm-uninstall
   ./install.sh
   ```
3. Check all system dependencies installed

### Issue: "Vision mode not working"
**Cause**: Camera not accessible or vision model not loaded  
**Solutions**:
1. Test camera: Run app with `--vision` flag and check camera window opens
2. Check vision keywords: "see", "look", "camera", "what is this", "describe"
3. Verify moondream model: `ollama list | grep moondream`
4. Check if vision model loads: Look for "Loading moondream" in console

### Issue: "GPU not being used"
**Cause**: PyTorch not compiled with CUDA or no GPU  
**Solutions**:
```bash
# Check if PyTorch sees GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# If False, reinstall PyTorch with CUDA
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

## Debug Mode

Enable verbose logging:

```python
# In main.py, add at top
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Getting Help

If issues persist:

1. Check logs: Look at console output for error messages
2. Verify versions:
   ```bash
   python --version  # Should be 3.9+
   ollama --version
   nvidia-smi        # If using NVIDIA GPU
   ```
3. Test components individually:
   ```bash
   # Test Ollama
   curl http://localhost:11434/api/generate -d '{"model":"gemma3","prompt":"Hello"}'
   
   # Test camera
   python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"
   
   # Test microphone
   python -c "import sounddevice as sd; print(sd.query_devices())"
   ```

## Performance Issues

### Text chat is slow (> 5 seconds)
- Check GPU is being used: Look for GPU memory usage
- Try smaller model: `talking-llm --model llama3.2`
- Close other GPU applications

### Vision is very slow (> 15 seconds)
- Normal on low-end GPUs (MX130, etc.)
- Check if model switching is happening (console messages)
- Consider `--keep-vision-loaded` if VRAM allows

### TTS is slow or choppy
- Piper runs on CPU, shouldn't be slow
- Check CPU usage: `top` or `htop`
- Try reducing audio quality in config

## Platform-Specific Issues

### macOS
- **Camera permissions**: Must grant in System Preferences
- **Microphone permissions**: Same as above
- **"App can't be opened"**: Run `xattr -cr /Applications/TalkingLLM.app`
- **PATH issues**: Add `export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc`

### Linux
- **Audio device busy**: Kill other apps using audio: `pulseaudio -k && pulseaudio --start`
- **Camera permission denied**: Add user to video group: `sudo usermod -a -G video $USER`
- **Wayland issues**: Some OpenCV features may not work on Wayland, try X11
- **No audio**: Check ALSA/PulseAudio: `alsamixer`, `pavucontrol`

## Error Messages Reference

| Error | Meaning | Solution |
|-------|---------|----------|
| `CUDA out of memory` | GPU VRAM full | Close other apps, check ResourceManager |
| `Connection refused` | Ollama not running | Start Ollama: `ollama serve` |
| `No such file or directory` | Missing files | Re-run installer |
| `Permission denied` | Missing permissions | Check camera/mic permissions |
| `ModuleNotFoundError` | Missing Python package | Activate venv, reinstall deps |
| `PortAudioError` | Audio system issue | Restart audio service |

## Recovery Procedures

### Complete Reinstall
```bash
# Uninstall
talking-llm-uninstall

# Remove all data
rm -rf ~/.local/share/talking-llm
rm -rf ~/.config/talking-llm
rm -rf ~/.cache/whisper

# Reinstall
curl -fsSL https://raw.githubusercontent.com/vndee/talking-llm-assistant/main/install.sh | bash
```

### Reset Configuration
```bash
rm ~/.config/talking-llm/config.yaml
# App will recreate with defaults on next run
```

### Clear GPU Memory
```bash
# If GPU is stuck
ollama stop gemma3 2>/dev/null || true
ollama stop moondream 2>/dev/null || true
python -c "import torch; torch.cuda.empty_cache()"
```

---

**For AI Assistants**: When helping users troubleshoot, always:
1. Check the most common issues first (Ollama, permissions)
2. Ask for specific error messages
3. Verify system requirements are met
4. Suggest checking `nvidia-smi` for GPU issues
