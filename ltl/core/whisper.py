"""Open-source voice transcription using Whisper.

Uses openai-whisper (MIT licensed, free) for local speech-to-text.
"""

import os
import sys
import tempfile
import numpy as np
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class WhisperTranscriber:
    """Open-source voice transcription using Whisper."""

    def __init__(self, model_name: str = "tiny"):
        self.model_name = model_name
        self.model = None

    def load_model(self):
        """Load the Whisper model."""
        if self.model is None:
            try:
                # Try to import from dedicated whisper venv
                import sys

                whisper_venv = os.path.expanduser("~/whisper-venv")
                if os.path.exists(whisper_venv):
                    # Try different Python versions
                    for py_ver in ["python3.14", "python3.13", "python3.12"]:
                        site_packages = os.path.join(whisper_venv, "lib", py_ver, "site-packages")
                        if os.path.exists(site_packages):
                            sys.path.insert(0, site_packages)
                            break

                import whisper

                print(f"🎤 Loading Whisper model: {self.model_name}")
                self.model = whisper.load_model(self.model_name)
                print("✅ Whisper model loaded")
            except ImportError as e:
                raise ImportError(f"openai-whisper not installed. Run: pip install openai-whisper. Error: {e}")

    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        """Transcribe audio data to text."""
        self.load_model()

        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        try:
            result = self.model.transcribe(audio_np, fp16=False)
            return result["text"].strip()
        except Exception as e:
            print(f"❌ Whisper transcription failed: {e}")
            return None

    def transcribe_file(self, audio_file_path: str) -> Optional[str]:
        """Transcribe audio from file."""
        self.load_model()

        try:
            result = self.model.transcribe(audio_file_path)
            return result["text"].strip()
        except Exception as e:
            print(f"❌ Whisper file transcription failed: {e}")
            return None


def create_whisper_transcriber(config: dict) -> Optional[WhisperTranscriber]:
    """Create Whisper transcriber from config."""
    voice_config = config.get("tools", {}).get("voice", {})

    if voice_config.get("transcription") != "whisper":
        return None

    model_name = voice_config.get("whisper_model", "tiny")

    try:
        transcriber = WhisperTranscriber(model_name)
        transcriber.load_model()  # Test loading
        print(f"✅ Whisper transcriber ready (model: {model_name})")
        return transcriber
    except Exception as e:
        print(f"❌ Failed to create Whisper transcriber: {e}")
        return None


def transcribe_audio_bytes(audio_bytes: bytes, config: dict = None) -> Optional[str]:
    """Transcribe audio bytes using configured transcriber."""
    if config is None:
        try:
            from ltl.core.config import load_config

            config = load_config()
        except:
            return None

    transcriber = create_whisper_transcriber(config)
    if transcriber:
        return transcriber.transcribe_audio(audio_bytes)

    return None


# Integration with channels
def setup_channel_transcription():
    """Set up voice transcription for channels."""
    try:
        from ltl.core.config import load_config

        config = load_config()

        # Enable whisper transcription
        if "tools" not in config:
            config["tools"] = {}
        if "voice" not in config["tools"]:
            config["tools"]["voice"] = {}

        config["tools"]["voice"]["transcription"] = "whisper"
        config["tools"]["voice"]["whisper_model"] = "tiny"

        from ltl.core.config import save_config

        save_config(config)

        print("✅ Voice transcription enabled with Whisper")
        print("   Model: tiny (fast, less accurate)")
        print("   For better accuracy, change to 'base' or 'small'")

    except Exception as e:
        print(f"❌ Failed to setup voice transcription: {e}")


if __name__ == "__main__":
    # Test Whisper transcription
    transcriber = WhisperTranscriber("tiny")

    # Create a simple test audio (silence)
    test_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence

    try:
        transcriber.load_model()
        print("✅ Whisper test: Model loaded successfully")

        # Test transcription (will be empty for silence)
        result = transcriber.transcribe_audio(test_audio.tobytes())
        print(f"Test transcription result: '{result}'")

    except Exception as e:
        print(f"❌ Whisper test failed: {e}")
        print("Install: pip install openai-whisper")
