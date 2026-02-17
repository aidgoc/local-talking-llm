"""Piper TTS wrapper for high-quality neural text-to-speech."""

import os
import numpy as np
from piper import PiperVoice

from src.logging_config import get_logger

log = get_logger(__name__)


_DEFAULT_VOICE = os.path.expanduser("~/.local/share/piper/en_US-lessac-medium.onnx")


class PiperTTSService:
    """Text-to-speech using Piper (CPU, ~60MB)."""

    def __init__(self, voice_path: str | None = None):
        path = os.path.expanduser(voice_path or _DEFAULT_VOICE)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Piper voice model not found: {path}\n"
                f"Download from: https://github.com/rhasspy/piper/releases"
            )
        self.voice = PiperVoice.load(path)
        self.sample_rate = self.voice.config.sample_rate

    def synthesize(self, text: str, **kwargs) -> tuple[int, np.ndarray]:
        """Synthesize text to audio.

        Returns:
            (sample_rate, audio_array) where audio_array is float32 numpy.
        """
        if not text or not text.strip():
            return self.sample_rate, np.array([], dtype=np.float32)

        chunks = list(self.voice.synthesize(text))
        if not chunks:
            return self.sample_rate, np.array([], dtype=np.float32)

        audio = np.concatenate([c.audio_float_array for c in chunks])
        return self.sample_rate, audio

    def long_form_synthesize(self, text: str, **kwargs) -> tuple[int, np.ndarray]:
        """Synthesize longer text. Piper handles sentence splitting internally."""
        return self.synthesize(text, **kwargs)
