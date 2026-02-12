"""
Wake Word Detection Module for Talking LLM Assistant

Provides simple keyword spotting for "Hey Assistant" using text matching.
Integrates with VAD for efficient background listening.

For AI Assistants:
- This module listens for wake words like "Hey Assistant"
- Uses Whisper transcription + keyword matching
- Integrates with VAD for power efficiency
- Provides configurable wake word options
"""

import threading
import time
import queue
import re
from typing import Optional, Callable, List
import sounddevice as sd
import numpy as np
import scipy.signal

# VAD import (optional - gracefully handles if not installed)
try:
    from src.vad import VoiceActivityDetector, AudioFrameBuffer, create_default_vad

    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False


class WakeWordDetector:
    """
    Wake Word Detection for "Hey Assistant" using keyword matching.

    Listens continuously for wake words in the background, then triggers
    a callback function when detected.

    Attributes:
        wake_words: List of wake word phrases to detect
        wake_callback: Function to call when wake word detected
        vad: Voice Activity Detector for efficient listening
        sample_rate: Audio sample rate (default: 16000 Hz)

    Example:
        >>> def on_wake_word_detected():
        ...     print("Wake word detected!")
        >>> detector = WakeWordDetector(on_wake_word_detected)
        >>> detector.start()  # Start background listening
        >>> # ... program runs ...
        >>> detector.stop()   # Stop listening
    """

    def __init__(
        self,
        wake_callback: Callable[[], None],
        console,
        wake_words: Optional[List[str]] = None,
        sample_rate: int = 16000,
        vad_aggressiveness: int = 3,  # Most aggressive to filter noise
        silence_timeout: float = 1.0,
        transcription_threshold: float = 0.7,  # Confidence threshold for wake word
    ):
        """
        Initialize wake word detector.

        Args:
            wake_callback: Function to call when wake word detected
            wake_words: List of wake word phrases (default: ["hey hng", "okay hng"])
            sample_rate: Audio sample rate in Hz (default: 16000)
            vad_aggressiveness: VAD mode for background listening (0-3, default: 3 most aggressive)
            silence_timeout: Seconds of silence before stopping a potential wake word sequence
            transcription_threshold: Minimum similarity score to trigger (0.0-1.0)
        """
        self.wake_callback = wake_callback
        self.wake_words = wake_words or [
            "hey hng",
            "okay hng",
        ]
        self.sample_rate = sample_rate
        self.vad_aggressiveness = vad_aggressiveness
        self.silence_timeout = silence_timeout
        self.transcription_threshold = transcription_threshold
        self.console = console

        # State
        self.is_listening = False
        self.listening_thread: Optional[threading.Thread] = None
        self.audio_queue = queue.Queue()
        self.vad: Optional[VoiceActivityDetector] = None
        self.frame_buffer: Optional[AudioFrameBuffer] = None

        # For wake word matching
        self.compiled_patterns = [
            re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            for word in self.wake_words
        ]

        # Precompute lowercase versions for fuzzy matching
        self.wake_words_lower = [word.lower() for word in self.wake_words]

    def _fuzzy_match(self, text: str, wake_word: str) -> float:
        """
        Calculate similarity score between text and wake word.

        Args:
            text: Transcribed text
            wake_word: Wake word to match against

        Returns:
            Similarity score between 0.0 and 1.0
        """
        text_lower = text.lower()
        wake_word_lower = wake_word.lower()

        # Exact match
        if wake_word_lower in text_lower:
            return 1.0

        # Check if all words appear in order (partial match)
        wake_parts = wake_word_lower.split()
        text_words = text_lower.split()

        if not wake_parts:
            return 0.0

        # Count matching words
        matches = 0
        text_idx = 0
        wake_idx = 0

        while text_idx < len(text_words) and wake_idx < len(wake_parts):
            if wake_parts[wake_idx] in text_words[text_idx]:
                matches += 1
                wake_idx += 1
            text_idx += 1

        return matches / len(wake_parts)

    def _check_wake_word(self, text: str) -> bool:
        """
        Check if text contains wake word.

        Args:
            text: Transcribed text

        Returns:
            True if wake word detected
        """
        # Check exact patterns first
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True

        # Fuzzy match if no exact match
        best_score = 0.0
        for wake_word in self.wake_words_lower:
            score = self._fuzzy_match(text, wake_word)
            best_score = max(best_score, score)

        return best_score >= self.transcription_threshold

    def _audio_callback(self, indata, frames, time_info, status):
        """
        Callback for audio stream. Processes audio for VAD and adds to queue.
        """
        if status:
            print(f"Audio status: {status}")

        # Add audio to queue for transcription
        self.audio_queue.put(bytes(indata))

        # Process with VAD for speech detection
        if VAD_AVAILABLE and self.vad and self.frame_buffer:
            frame = self.frame_buffer.add_audio(bytes(indata))
            if frame:
                try:
                    result = self.vad.process_frame(frame)
                    # VAD processing for wake word detection
                    # (We'll handle this in the processing thread)
                except Exception:
                    # Silently ignore VAD errors in background listening
                    pass

    def _process_audio(self, stt):
        """
        Background thread for processing audio and detecting wake words.

        Args:
            stt: Whisper model for speech-to-text
        """
        # Buffer for accumulating audio across VAD segments
        audio_buffer = []
        buffer_size = 0
        max_buffer_duration = 3.0  # Maximum audio to keep for transcription
        max_buffer_samples = int(max_buffer_duration * self.sample_rate)

        # Track speech state
        in_speech_segment = False
        speech_start_time = None
        last_audio_time = time.time()

        self.console.print("[dim]🔍 Wake word detector listening...[/dim]")

        while self.is_listening:
            try:
                # Get audio data (with timeout for responsive shutdown)
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    # Check if we should stop
                    if not self.is_listening:
                        break
                    continue

                # Add to buffer
                audio_buffer.append(audio_chunk)
                buffer_size += len(audio_chunk) // 2  # 16-bit = 2 bytes per sample

                # Trim buffer if too large
                while buffer_size > max_buffer_samples and len(audio_buffer) > 1:
                    removed = audio_buffer.pop(0)
                    buffer_size -= len(removed) // 2

                # Convert audio chunks to numpy for VAD processing
                if VAD_AVAILABLE and self.vad and self.frame_buffer:
                    audio_np = (
                        np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
                        / 32768.0
                    )
                    if self.sample_rate != 16000:
                        resampled_audio = scipy.signal.resample(
                            audio_np, int(len(audio_np) * 16000 / self.sample_rate)
                        )
                    else:
                        resampled_audio = audio_np

                    # Get frame from buffer
                    frame = self.frame_buffer.add_audio(
                        resampled_audio.astype(np.int16).tobytes()
                    )
                    if frame:
                        result = self.vad.process_frame(frame)

                        if result["is_speech"]:
                            if not in_speech_segment:
                                in_speech_segment = True
                                speech_start_time = time.time()
                                self.console.print("[dim]🔊 Speech detected...[/dim]")
                        else:
                            # Check if speech segment has ended
                            if in_speech_segment and result["should_stop"]:
                                in_speech_segment = False

                                # We have a complete speech segment, transcribe it
                                if audio_buffer and buffer_size > 0:
                                    # Combine all audio in buffer
                                    combined_bytes = b"".join(audio_buffer)
                                    audio_np = (
                                        np.frombuffer(
                                            combined_bytes, dtype=np.int16
                                        ).astype(np.float32)
                                        / 32768.0
                                    )

                                    # Transcribe
                                    try:
                                        result = stt.transcribe(audio_np, fp16=False)
                                        text = result["text"].strip().lower()

                                        if text:
                                            self.console.print(
                                                f"[dim]📝 Heard: {text}[/dim]"
                                            )

                                            # Check for wake word
                                            if self._check_wake_word(text):
                                                self.console.print(
                                                    "[green]🎯 Wake word detected![/green]"
                                                )
                                                # Clear buffer and trigger callback
                                                audio_buffer.clear()
                                                buffer_size = 0
                                                self.wake_callback()

                                        # Clear buffer after transcription
                                        audio_buffer.clear()
                                        buffer_size = 0

                                    except Exception as e:
                                        self.console.print(
                                            f"[yellow]Transcription error: {e}[/yellow]"
                                        )
                                        audio_buffer.clear()
                                        buffer_size = 0

                last_audio_time = time.time()

            except Exception as e:
                self.console.print(f"[yellow]Wake word processing error: {e}[/yellow]")
                time.sleep(0.1)

    def start(self, stt):
        """
        Start background listening for wake words.

        Args:
            stt: Whisper model for speech-to-text
        """
        if self.is_listening:
            self.console.print("[yellow]Wake word detector already running[/yellow]")
            return

        self.is_listening = True

        # Initialize VAD if available
        if VAD_AVAILABLE:
            try:
                self.vad = VoiceActivityDetector(
                    aggressiveness=self.vad_aggressiveness,
                    sample_rate=16000,  # VAD supports 8000, 16000, 32000, 48000
                    frame_duration_ms=30,
                    silence_timeout=self.silence_timeout,
                )
                self.frame_buffer = AudioFrameBuffer(frame_size=self.vad.frame_size)
            except Exception as e:
                self.console.print(f"[yellow]VAD initialization failed: {e}[/yellow]")
                self.vad = None
                self.frame_buffer = None

        # Start audio stream
        self.audio_stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
            blocksize=1024,  # Smaller blocks for lower latency
        )
        self.audio_stream.start()

        # Start processing thread
        self.listening_thread = threading.Thread(
            target=self._process_audio, args=(stt,), daemon=True
        )
        self.listening_thread.start()

        self.console.print("[green]✅ Wake word detector started[/green]")

    def stop(self):
        """Stop background listening."""
        if not self.is_listening:
            return

        self.is_listening = False

        # Stop audio stream
        if hasattr(self, "audio_stream"):
            self.audio_stream.stop()
            self.audio_stream.close()

        # Wait for thread to finish
        if self.listening_thread:
            self.listening_thread.join(timeout=2.0)

        self.console.print("[yellow]⏹️ Wake word detector stopped[/yellow]")

    def add_wake_word(self, wake_word: str):
        """Add a new wake word to detect."""
        self.wake_words.append(wake_word)
        self.compiled_patterns.append(
            re.compile(rf"\b{re.escape(wake_word)}\b", re.IGNORECASE)
        )
        self.wake_words_lower.append(wake_word.lower())

    def remove_wake_word(self, wake_word: str):
        """Remove a wake word from detection."""
        try:
            idx = self.wake_words.index(wake_word)
            self.wake_words.pop(idx)
            self.compiled_patterns.pop(idx)
            self.wake_words_lower.pop(idx)
        except ValueError:
            pass


# Test function
if __name__ == "__main__":
    import whisper

    def wake_word_detected():
        print("=" * 50)
        print("WAKE WORD DETECTED!")
        print("=" * 50)

    # Load Whisper (tiny model for testing)
    print("Loading Whisper model...")
    stt = whisper.load_model("tiny.en")

    # Create detector
    detector = WakeWordDetector(
        wake_callback=wake_word_detected,
        wake_words=["hey hng", "okay hng"],
        transcription_threshold=0.6,  # Lower threshold for testing
    )

    try:
        print("Starting wake word detector. Say 'Hey HNG' to trigger.")
        print("Press Ctrl+C to stop.")
        detector.start(stt)

        # Keep running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        detector.stop()
