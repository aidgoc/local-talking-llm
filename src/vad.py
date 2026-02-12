"""
Voice Activity Detection (VAD) Module for Talking LLM Assistant

Provides automatic speech detection to stop recording when user stops speaking.
Uses WebRTC VAD for efficient, real-time voice activity detection.

For AI Assistants:
- This module detects speech vs silence in audio streams
- Integrates with the recording system to auto-stop after silence
- Configurable aggressiveness (0-3) and silence timeout
"""

import webrtcvad
import collections
import time
from typing import Optional


class VoiceActivityDetector:
    """
    Voice Activity Detection using WebRTC VAD.

    Detects speech in audio frames and determines when to stop recording
    based on continuous silence duration.

    Attributes:
        vad: WebRTC VAD instance
        aggressiveness: VAD aggressiveness (0-3, higher = more aggressive filtering)
        frame_duration_ms: Frame duration in milliseconds (must be 10, 20, or 30)
        sample_rate: Audio sample rate (must be 8000, 16000, 32000, or 48000)
        silence_timeout: Seconds of silence before stopping (configurable)

    Example:
        >>> vad = VoiceActivityDetector(aggressiveness=2, silence_timeout=1.5)
        >>> vad.is_speech(audio_frame_bytes)
        True
    """

    def __init__(
        self,
        aggressiveness: int = 2,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        silence_timeout: float = 1.5,
    ):
        """
        Initialize VAD with specified parameters.

        Args:
            aggressiveness: VAD mode (0-3).
                0: Least aggressive, detects more speech
                3: Most aggressive, detects less speech
                Default: 2 (balanced)
            sample_rate: Audio sample rate in Hz.
                Must be 8000, 16000, 32000, or 48000
                Default: 16000 (matches Whisper)
            frame_duration_ms: Frame size in ms.
                Must be 10, 20, or 30 ms
                Default: 30 ms
            silence_timeout: Seconds of silence before auto-stop.
                Default: 1.5 seconds

        Raises:
            ValueError: If parameters are invalid
        """
        if aggressiveness not in [0, 1, 2, 3]:
            raise ValueError("Aggressiveness must be 0, 1, 2, or 3")

        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("Sample rate must be 8000, 16000, 32000, or 48000 Hz")

        if frame_duration_ms not in (10, 20, 30):
            raise ValueError("Frame duration must be 10, 20, or 30 ms")

        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.silence_timeout = silence_timeout

        # State tracking
        self.last_speech_time: Optional[float] = None
        self.silence_start_time: Optional[float] = None
        self.is_speaking = False

    def is_speech(self, frame: bytes) -> bool:
        """
        Check if audio frame contains speech.

        Args:
            frame: Audio frame bytes (must match frame_size)

        Returns:
            True if speech detected, False if silence

        Raises:
            ValueError: If frame size doesn't match expected size
        """
        if len(frame) != self.frame_size * 2:  # 16-bit = 2 bytes per sample
            raise ValueError(
                f"Frame size mismatch. Expected {self.frame_size * 2} bytes, "
                f"got {len(frame)} bytes"
            )

        return self.vad.is_speech(frame, self.sample_rate)

    def process_frame(self, frame: bytes) -> dict:
        """
        Process a frame and update speech state.

        Args:
            frame: Audio frame bytes

        Returns:
            Dictionary with:
                - is_speech: Whether current frame has speech
                - is_speaking: Whether user is currently speaking
                - silence_duration: How long silence has lasted (seconds)
                - should_stop: Whether to stop recording
        """
        current_time = time.time()
        speech_detected = self.is_speech(frame)

        result = {
            "is_speech": speech_detected,
            "is_speaking": False,
            "silence_duration": 0.0,
            "should_stop": False,
        }

        if speech_detected:
            # Speech detected
            self.is_speaking = True
            self.last_speech_time = current_time
            self.silence_start_time = None
            result["is_speaking"] = True
        else:
            # Silence detected
            if self.is_speaking:
                # Just stopped speaking
                if self.silence_start_time is None:
                    self.silence_start_time = current_time

                silence_duration = current_time - self.silence_start_time
                result["silence_duration"] = silence_duration

                # Check if we should stop
                if silence_duration >= self.silence_timeout:
                    result["should_stop"] = True
                    self.is_speaking = False
                    self.silence_start_time = None
            else:
                # Still not speaking
                result["is_speaking"] = False

        return result

    def reset(self):
        """Reset VAD state for new recording session."""
        self.last_speech_time = None
        self.silence_start_time = None
        self.is_speaking = False


class AudioFrameBuffer:
    """
    Buffer for collecting audio frames before VAD processing.

    Handles conversion from continuous audio stream to discrete frames
    suitable for WebRTC VAD.
    """

    def __init__(self, frame_size: int):
        """
        Initialize buffer.

        Args:
            frame_size: Number of samples per frame
        """
        self.frame_size = frame_size
        self.buffer = bytearray()

    def add_audio(self, audio_bytes: bytes) -> Optional[bytes]:
        """
        Add audio data to buffer and return complete frames.

        Args:
            audio_bytes: Raw audio bytes to add

        Returns:
            Complete frame bytes if enough data, None otherwise
        """
        self.buffer.extend(audio_bytes)

        frame_byte_size = self.frame_size * 2  # 16-bit audio

        if len(self.buffer) >= frame_byte_size:
            frame = bytes(self.buffer[:frame_byte_size])
            self.buffer = self.buffer[frame_byte_size:]
            return frame

        return None

    def reset(self):
        """Clear the buffer."""
        self.buffer = bytearray()


# Convenience function for simple use cases
def create_default_vad(silence_timeout: float = 1.5) -> VoiceActivityDetector:
    """
    Create a VAD with default settings optimized for Talking LLM Assistant.

    Args:
        silence_timeout: Seconds of silence before auto-stop

    Returns:
        Configured VoiceActivityDetector instance
    """
    return VoiceActivityDetector(
        aggressiveness=2,  # Balanced
        sample_rate=16000,  # Matches Whisper
        frame_duration_ms=30,  # Good balance of accuracy and latency
        silence_timeout=silence_timeout,
    )


# Example usage
if __name__ == "__main__":
    # Create VAD
    vad = create_default_vad(silence_timeout=1.0)

    # Simulate processing (in real use, this comes from microphone)
    print("VAD initialized successfully!")
    print(f"Frame size: {vad.frame_size} samples")
    print(f"Frame duration: {vad.frame_duration_ms} ms")
    print(f"Silence timeout: {vad.silence_timeout} seconds")

    # Test with silence (all zeros)
    silence_frame = bytes(vad.frame_size * 2)  # 16-bit silence
    result = vad.process_frame(silence_frame)
    print(f"\nSilence frame: is_speech={result['is_speech']}")

    # Note: To test with real audio, integrate with sounddevice recording
    print("\nVAD module ready for integration!")
