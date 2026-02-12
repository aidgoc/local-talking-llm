# How to Run Talking LLM HNG

## Quick Start

```bash
# 1. Start Ollama server in a separate terminal
ollama serve

# 2. Start the application with wake word detection:
cd /home/harshwardhan/local-talking-llm
./run_optimized.sh

# OR use the test script:
./test_hng.sh
```

## Wake Words

The wake words are:
- **"hey hng"**
- **"okay hng"**

Say either one to activate the assistant.

## Options

### Basic Mode
```bash
./run_optimized.sh
```
- Enables wake word, VAD, vision, and performance monitoring

### Voice Activity Detection (VAD) Only
```bash
./run_optimized.sh --use-vad --silence-timeout 1.5
```
- Auto-stops recording after 1.5 seconds of silence

### Wake Word Only
```bash
./run_optimized.sh --wake-word
```
- Continuous listening for "hey hng" or "okay hng"

### Performance Metrics
```bash
./run_optimized.sh --perf
```
- Shows timing for all components

### Lightweight Testing
```bash
./test_hng.sh
```
- Simpler version with wake word + tiny Whisper model

## Troubleshooting

### CUDA Errors
- The app is designed to use CPU for Whisper
- Only the LLM needs GPU
- "Device not compatible" warnings for PyTorch are normal

### No Response
- Ensure Ollama is running: `ollama serve`
- Check if Ollama has the models: `ollama list`
- Pull models if needed: `ollama pull gemma3 moondream`

### Microphone Issues
- Check permissions
- Test with: `python -m sounddevice`