"""Tests for health checks with mocked external dependencies."""

from unittest.mock import MagicMock, patch

from src.health import (
    CheckResult,
    HealthReport,
    check_audio_devices,
    check_ollama,
    check_piper_voice,
    run_health_checks,
)


def test_health_report_no_failure():
    report = HealthReport(checks=[
        CheckResult("Test", "pass", "OK"),
        CheckResult("Test2", "warn", "minor issue"),
    ])
    assert not report.has_critical_failure


def test_health_report_with_failure():
    report = HealthReport(checks=[
        CheckResult("Test", "pass", "OK"),
        CheckResult("Ollama", "fail", "unreachable"),
    ])
    assert report.has_critical_failure


def test_health_report_summary_lines():
    report = HealthReport(checks=[CheckResult("Ollama", "pass", "Connected")])
    lines = report.summary_lines()
    assert len(lines) == 1
    assert "Ollama" in lines[0]


def test_check_ollama_connected():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "gemma3:latest"}, {"name": "moondream:latest"}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("src.health.requests.get", return_value=mock_resp):
        results = check_ollama("http://localhost:11434", "gemma3", "moondream")

    statuses = {r.name: r.status for r in results}
    assert statuses["Ollama"] == "pass"
    assert statuses["Model 'gemma3'"] == "pass"
    assert statuses["Model 'moondream'"] == "pass"


def test_check_ollama_unreachable():
    import requests
    with patch("src.health.requests.get", side_effect=requests.ConnectionError()):
        results = check_ollama("http://localhost:11434", "gemma3")

    assert results[0].status == "fail"
    assert "Cannot connect" in results[0].detail


def test_check_ollama_model_missing():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "gemma3:latest"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.health.requests.get", return_value=mock_resp):
        results = check_ollama("http://localhost:11434", "gemma3", "moondream")

    statuses = {r.name: r.status for r in results}
    assert statuses["Model 'gemma3'"] == "pass"
    assert statuses["Model 'moondream'"] == "warn"


def test_check_audio_devices_found():
    mock_devices = [{"name": "Mic", "max_input_channels": 2, "max_output_channels": 0}]
    with patch("src.health.sd.query_devices", return_value=mock_devices):
        result = check_audio_devices()
    assert result.status == "pass"


def test_check_audio_devices_none():
    mock_devices = [{"name": "Speaker", "max_input_channels": 0, "max_output_channels": 2}]
    with patch("src.health.sd.query_devices", return_value=mock_devices):
        result = check_audio_devices()
    assert result.status == "fail"


def test_check_piper_voice_exists(tmp_path):
    voice_file = tmp_path / "voice.onnx"
    voice_file.touch()
    result = check_piper_voice(str(voice_file))
    assert result.status == "pass"


def test_check_piper_voice_missing():
    result = check_piper_voice("/nonexistent/voice.onnx")
    assert result.status == "warn"


def test_run_health_checks_ollama_backend():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "gemma3:latest"}]}
    mock_resp.raise_for_status = MagicMock()

    mock_devices = [{"name": "Mic", "max_input_channels": 2, "max_output_channels": 0}]

    config = {
        "backend": "ollama",
        "ollama": {"base_url": "http://localhost:11434", "text_model": "gemma3"},
        "camera": {"enabled": True},
        "tts": {"piper": {"voice_path": "/nonexistent/voice.onnx"}},
    }

    with patch("src.health.requests.get", return_value=mock_resp), \
         patch("src.health.sd.query_devices", return_value=mock_devices):
        report = run_health_checks(config)

    names = [c.name for c in report.checks]
    assert "Ollama" in names
    assert "Audio input" in names
    assert "Piper voice" in names
