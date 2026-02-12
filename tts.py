"""Text-to-speech service using Piper neural TTS."""

import numpy as np
from src.piper_tts import PiperTTSService


class TextToSpeechService:
    """TTS service backed by Piper. Drop-in replacement for the old pyttsx3 version."""

    def __init__(self, voice_path: str | None = None, **kwargs):
        self._backend = PiperTTSService(voice_path)
        self.sample_rate = self._backend.sample_rate

    def synthesize(self, text: str, **kwargs) -> tuple[int, np.ndarray]:
        return self._backend.synthesize(text)

    def long_form_synthesize(self, text: str, **kwargs) -> tuple[int, np.ndarray]:
        return self._backend.long_form_synthesize(text)
