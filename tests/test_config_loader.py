"""Tests for config loading, validation, and env overrides."""

import os
import tempfile

import yaml

from src.config_loader import (
    _apply_env_overrides,
    _deep_merge,
    _expand_paths,
    load_config,
    validate_config,
)


def test_deep_merge_basic():
    base = {"a": 1, "b": {"c": 2}}
    override = {"b": {"d": 3}, "e": 4}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}


def test_deep_merge_override_value():
    base = {"a": 1}
    override = {"a": 2}
    assert _deep_merge(base, override) == {"a": 2}


def test_expand_paths():
    config = {"path": "~/data", "nested": {"path": "~/more"}, "num": 42}
    result = _expand_paths(config)
    assert "~" not in result["path"]
    assert "~" not in result["nested"]["path"]
    assert result["num"] == 42


def test_apply_env_overrides(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
    monkeypatch.setenv("LLM_BACKEND", "openrouter")
    config = {}
    result = _apply_env_overrides(config)
    assert result["openrouter"]["api_key"] == "test-key-123"
    assert result["backend"] == "openrouter"


def test_apply_env_overrides_no_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    config = {"backend": "ollama"}
    result = _apply_env_overrides(config)
    assert result["backend"] == "ollama"


def test_load_config_from_file():
    config_data = {
        "backend": "ollama",
        "ollama": {"text_model": "gemma3"},
        "database": {"path": "/tmp/test.db"},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        path = f.name

    try:
        config = load_config(path)
        assert config["backend"] == "ollama"
        assert config["ollama"]["text_model"] == "gemma3"
    finally:
        os.unlink(path)


def test_load_config_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


# -- Validation --

def test_validate_config_valid():
    config = {
        "backend": "ollama",
        "whisper": {"model": "base.en"},
        "database": {"path": "/tmp/test.db"},
        "ollama": {"base_url": "http://localhost:11434"},
    }
    errors = validate_config(config)
    assert errors == []


def test_validate_config_invalid_backend():
    config = {"backend": "invalid", "whisper": {"model": "base.en"}, "database": {"path": "/tmp/t.db"}}
    errors = validate_config(config)
    assert any("backend" in e.lower() for e in errors)


def test_validate_config_invalid_whisper():
    config = {"backend": "ollama", "whisper": {"model": "huge"}, "database": {"path": "/tmp/t.db"}}
    errors = validate_config(config)
    assert any("whisper" in e.lower() for e in errors)


def test_validate_config_openrouter_no_key():
    config = {
        "backend": "openrouter",
        "whisper": {"model": "base.en"},
        "database": {"path": "/tmp/t.db"},
        "openrouter": {"api_key": ""},
    }
    errors = validate_config(config)
    assert any("api key" in e.lower() for e in errors)


def test_validate_config_empty_db_path():
    config = {"backend": "ollama", "whisper": {"model": "base.en"}, "database": {"path": ""}}
    errors = validate_config(config)
    assert any("database" in e.lower() for e in errors)
