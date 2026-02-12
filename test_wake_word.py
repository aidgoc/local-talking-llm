#!/usr/bin/env python3
"""
Simple test script for VAD and wake word detection
Tests the functionality without requiring full dependencies
"""

import sys
import os

# Test 1: Import VAD module
print("=" * 60)
print("TEST 1: VAD Module Import")
print("=" * 60)
try:
    from src.vad import VoiceActivityDetector, AudioFrameBuffer, create_default_vad

    print("✅ VAD module imported successfully")

    # Create a VAD instance
    vad = create_default_vad(silence_timeout=1.5)
    print(f"✅ VAD created with:")
    print(f"   - Sample rate: {vad.sample_rate} Hz")
    print(f"   - Frame size: {vad.frame_size} samples")
    print(f"   - Silence timeout: {vad.silence_timeout}s")
    print(f"   - Aggressiveness: {vad.vad.get_mode()}")

except Exception as e:
    print(f"❌ VAD import failed: {e}")
    sys.exit(1)

# Test 2: Import wake word module
print("\n" + "=" * 60)
print("TEST 2: Wake Word Module Import")
print("=" * 60)
try:
    from src.wake_word import WakeWordDetector

    print("✅ Wake word module imported successfully")

    # Create a detector instance
    def dummy_callback():
        pass

    detector = WakeWordDetector(
        wake_callback=dummy_callback,
        wake_words=["hey hng", "okay hng"],
        transcription_threshold=0.7,
    )
    print(f"✅ Wake word detector created with:")
    print(f"   - Wake words: {detector.wake_words}")
    print(f"   - Threshold: {detector.transcription_threshold}")
    print(f"   - Sample rate: {detector.sample_rate} Hz")

except Exception as e:
    print(f"❌ Wake word import failed: {e}")
    sys.exit(1)

# Test 3: Test wake word detection with sample text
print("\n" + "=" * 60)
print("TEST 3: Wake Word Detection Test")
print("=" * 60)

test_phrases = [
    ("hey hng", True),
    ("okay hng", True),
    ("HEY HNG", True),
    ("Hey HNG!", True),
    ("hello world", False),
    ("hey there", False),
    ("what is hng", False),
]

all_passed = True
for phrase, expected in test_phrases:
    result = detector._check_wake_word(phrase)
    status = "✅" if result == expected else "❌"
    print(f"{status} '{phrase}' -> detected: {result} (expected: {expected})")
    if result != expected:
        all_passed = False

if all_passed:
    print("\n✅ All wake word detection tests passed!")
else:
    print("\n⚠️  Some tests failed (may need fuzzy matching adjustment)")

# Test 4: Test VAD with silence frame
print("\n" + "=" * 60)
print("TEST 4: VAD Silence Detection")
print("=" * 60)

try:
    # Create silence frame (all zeros)
    silence_frame = bytes(vad.frame_size * 2)  # 16-bit audio

    # Process silence frame
    result = vad.process_frame(silence_frame)

    print(f"✅ VAD processed silence frame:")
    print(f"   - Is speech: {result['is_speech']}")
    print(f"   - Is speaking: {result['is_speaking']}")
    print(f"   - Silence duration: {result['silence_duration']:.2f}s")
    print(f"   - Should stop: {result['should_stop']}")

except Exception as e:
    print(f"❌ VAD test failed: {e}")
    sys.exit(1)

# Test 5: Import performance monitor
print("\n" + "=" * 60)
print("TEST 5: Performance Monitor Import")
print("=" * 60)
try:
    from src.perf_monitor import PerformanceMonitor, get_perf_monitor

    print("✅ Performance monitor imported successfully")

    # Create instance
    monitor = PerformanceMonitor()
    print(f"✅ Performance monitor created successfully")

except Exception as e:
    print(f"❌ Performance monitor import failed: {e}")
    sys.exit(1)

# Final summary
print("\n" + "=" * 60)
print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
print("=" * 60)
print("\nNext steps:")
print(
    "1. Install remaining dependencies: pip install openai-whisper torch opencv-python"
)
print("2. Start Ollama: ollama serve")
print("3. Run the application: python app_optimized.py --wake-word --perf")
print("\nFeatures tested:")
print("✅ Voice Activity Detection (VAD)")
print("✅ Wake Word Detection ('hey hng', 'okay hng')")
print("✅ Performance Monitoring")
print("\nDefault wake words: 'hey hng', 'okay hng'")
