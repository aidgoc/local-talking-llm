"""Text-to-speech service using Piper neural TTS with automatic resampling."""

import numpy as np
from math import gcd
from scipy.signal import resample_poly
import sounddevice as sd
from src.piper_tts import PiperTTSService
from src.logging_config import get_logger

log = get_logger(__name__)


class TextToSpeechService:
    """TTS service backed by Piper with automatic resampling to device rate."""

    def __init__(self, voice_path: str | None = None, **kwargs):
        self._backend = PiperTTSService(voice_path)
        self.sample_rate = self._backend.sample_rate
        self.target_sample_rate = self._get_device_sample_rate()
        log.info(f"TTS initialized with source rate: {self.sample_rate}Hz, target rate: {self.target_sample_rate}Hz")

    def _get_device_sample_rate(self) -> int:
        """Get the default output device's native sample rate."""
        try:
            info = sd.query_devices(sd.default.device[1], "output")
            return int(info["default_samplerate"])
        except Exception as e:
            log.warning(f"Error getting device sample rate: {e}, using 44100Hz as fallback")
            return 44100  # Common fallback

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio with multiple fallback methods."""
        if orig_sr == target_sr:
            return audio

        log.debug(f"Resampling from {orig_sr}Hz to {target_sr}Hz")

        try:
            # Try resampy first if available (higher quality)
            try:
                import resampy

                return resampy.resample(audio, orig_sr, target_sr)
            except ImportError:
                # Fall back to scipy
                factor = gcd(orig_sr, target_sr)
                up = target_sr // factor
                down = orig_sr // factor
                return resample_poly(audio, up, down).astype(np.float32)
        except Exception as e:
            log.warning(f"Advanced resampling failed: {e}, using simple interpolation")
            # Last resort: simple linear interpolation
            return np.interp(
                np.linspace(0, len(audio) - 1, int(len(audio) * target_sr / orig_sr)), np.arange(len(audio)), audio
            ).astype(np.float32)

    def synthesize(self, text: str, **kwargs) -> tuple[int, np.ndarray]:
        """Synthesize text to audio and resample to device rate."""
        if not text or not text.strip():
            return self.target_sample_rate, np.array([], dtype=np.float32)

        try:
            source_rate, audio = self._backend.synthesize(text)

            # Always resample to the device's preferred rate
            if source_rate != self.target_sample_rate:
                audio = self._resample(audio, source_rate, self.target_sample_rate)

            return self.target_sample_rate, audio
        except Exception as e:
            log.error(f"TTS synthesis failed: {e}")
            # Return empty audio on failure
            return self.target_sample_rate, np.array([], dtype=np.float32)

    def long_form_synthesize(self, text: str, **kwargs) -> tuple[int, np.ndarray]:
        """Synthesize longer text with resampling."""
        return self.synthesize(text, **kwargs)
