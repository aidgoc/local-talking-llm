# TTS Fix for Local-Talking-LLM

This document explains the fix for the Text-to-Speech (TTS) issues you were experiencing with the local-talking-llm project.

## The Problem

The errors you encountered were related to sample rate mismatches between:
1. The Piper TTS output (22050 Hz)
2. Your audio device's supported sample rates (44100 Hz)

This resulted in errors like:
```
Expression 'paInvalidSampleRate' failed in 'src/hostapi/alsa/pa_linux_alsa.c'
Error opening OutputStream: Invalid sample rate [PaErrorCode -9997]
```

## The Solution

I've created an enhanced TTS module that automatically handles resampling to your device's native sample rate. The key improvements are:

1. **Automatic Sample Rate Detection**: The TTS service now detects your audio device's native sample rate at initialization
2. **Robust Resampling**: Multiple resampling methods with fallbacks for reliability
3. **Error Handling**: Better error messages and graceful degradation

## Files Created/Modified

1. **tts.py** (Modified): Enhanced with automatic resampling
2. **app_optimized.py** (Modified): Updated to use the enhanced TTS directly
3. **run_ltl_fixed.sh** (New): Script to run LTL with the fixed TTS
4. **test_enhanced_tts.py** (New): Test script for the enhanced TTS
5. **tts_fix.py** (New): Diagnostic script that helped identify the issue

## How to Use the Fix

1. Run the fixed version:
   ```bash
   ./run_ltl_fixed.sh
   ```

2. Test just the TTS component:
   ```bash
   python test_enhanced_tts.py
   ```

## Technical Details

### Sample Rate Handling

The enhanced TTS module now:
1. Detects your audio device's native sample rate (44100 Hz in your case)
2. Automatically resamples Piper's output (22050 Hz) to match your device
3. Uses multiple resampling methods with fallbacks:
   - resampy (if available)
   - scipy.signal.resample_poly
   - Simple linear interpolation (last resort)

### Error Handling

The module now has better error handling:
1. Graceful fallbacks for sample rate detection
2. Multiple resampling methods if one fails
3. Clear error messages for troubleshooting

## Recording Fix Applied

In addition to the TTS playback fix, we also fixed the recording issue:

### The Recording Problem
- Voice recording was hardcoded to 16000 Hz
- Your audio device only supports 44100 Hz input
- This caused the same "paInvalidSampleRate" errors during recording

### The Recording Solution
- **Automatic sample rate detection**: Detect input device's native rate (44100 Hz)
- **Dynamic resampling**: Resample from device rate (44100 Hz) to 16000 Hz for Whisper
- **Same robust resampling**: Uses the same multi-method approach as TTS

### Fixed Components
- `ltl/commands/tui.py`: Voice recording in TUI interface
- `/speak` and `/record` commands in the LTL CLI

## Future Improvements

For even better audio performance, consider:

1. Installing resampy for higher quality resampling:
   ```bash
   pip install resampy
   ```

2. Using a Piper voice model that matches your device's native sample rate (if available)

3. Configuring ALSA to support 22050 Hz directly (advanced)

## Troubleshooting

If you still encounter issues:

1. Check your audio device configuration:
   ```bash
   python -c "import sounddevice as sd; print(sd.query_devices())"
   ```

2. Try forcing a specific sample rate:
   ```bash
   AUDIODEV=plughw:0,0 python app_optimized.py
   ```

3. Run the diagnostic script:
   ```bash
   python tts_fix.py
   ```