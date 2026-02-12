"""Startup health checks for required services and hardware."""

import os
from dataclasses import dataclass, field

import requests
import sounddevice as sd

from src.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class CheckResult:
    name: str
    status: str  # "pass", "fail", "warn"
    detail: str = ""


@dataclass
class HealthReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def has_critical_failure(self) -> bool:
        return any(c.status == "fail" for c in self.checks)

    def summary_lines(self) -> list[str]:
        lines = []
        for c in self.checks:
            icon = {"pass": "[green]PASS[/green]", "fail": "[red]FAIL[/red]", "warn": "[yellow]WARN[/yellow]"}
            lines.append(f"  {icon.get(c.status, c.status):>20s}  {c.name}: {c.detail}")
        return lines


def check_ollama(base_url: str, text_model: str, vision_model: str | None = None) -> list[CheckResult]:
    """Check Ollama connectivity and model availability."""
    results = []

    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.ConnectionError:
        results.append(CheckResult("Ollama", "fail", f"Cannot connect to {base_url}"))
        return results
    except Exception as e:
        results.append(CheckResult("Ollama", "fail", f"Error: {e}"))
        return results

    results.append(CheckResult("Ollama", "pass", f"Connected to {base_url}"))

    available = {m["name"].split(":")[0] for m in resp.json().get("models", [])}

    if text_model in available:
        results.append(CheckResult(f"Model '{text_model}'", "pass", "Available"))
    else:
        results.append(CheckResult(f"Model '{text_model}'", "fail", f"Not pulled. Run: ollama pull {text_model}"))

    if vision_model:
        if vision_model in available:
            results.append(CheckResult(f"Model '{vision_model}'", "pass", "Available"))
        else:
            results.append(
                CheckResult(f"Model '{vision_model}'", "warn", f"Not pulled. Run: ollama pull {vision_model}")
            )

    return results


def check_audio_devices() -> CheckResult:
    """Check that an audio input device is available."""
    try:
        devices = sd.query_devices()
        # Handle different return types from sounddevice (list, DeviceList, dict)
        if isinstance(devices, dict):
            # Single device returned as dict
            has_input = devices.get("max_input_channels", 0) > 0
        else:
            # List, DeviceList, or other iterable - convert to list
            device_list = list(devices) if not isinstance(devices, list) else devices
            has_input = any(d.get("max_input_channels", 0) > 0 for d in device_list if isinstance(d, dict))

        if has_input:
            return CheckResult("Audio input", "pass", "Microphone available")
        return CheckResult("Audio input", "warn", "No input device found (will use text mode)")
    except Exception as e:
        return CheckResult("Audio input", "warn", f"Audio check failed: {e}")


def check_piper_voice(voice_path: str) -> CheckResult:
    """Check that the Piper voice model file exists."""
    path = os.path.expanduser(voice_path)
    if os.path.exists(path):
        return CheckResult("Piper voice", "pass", f"Found {os.path.basename(path)}")
    return CheckResult("Piper voice", "warn", f"Not found: {path} (TTS will be disabled)")


def run_health_checks(config: dict) -> HealthReport:
    """Run all startup health checks and return a report."""
    report = HealthReport()
    backend = config.get("backend", "ollama")

    # Ollama check (only if using local backend)
    if backend in ("ollama", "auto"):
        ollama_cfg = config.get("ollama", {})
        base_url = ollama_cfg.get("base_url", "http://localhost:11434")
        text_model = ollama_cfg.get("text_model", "gemma3")
        vision_model = ollama_cfg.get("vision_model")
        if not config.get("camera", {}).get("enabled", True):
            vision_model = None
        report.checks.extend(check_ollama(base_url, text_model, vision_model))

    # Audio input
    report.checks.append(check_audio_devices())

    # Piper voice
    voice_path = (
        config.get("tts", {}).get("piper", {}).get("voice_path", "~/.local/share/piper/en_US-lessac-medium.onnx")
    )
    report.checks.append(check_piper_voice(voice_path))

    return report
