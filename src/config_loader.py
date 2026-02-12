"""Configuration loader with YAML defaults and environment variable overrides."""

import os
import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _expand_paths(config: dict) -> dict:
    """Expand ~ in any string values that look like paths."""
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = _expand_paths(value)
        elif isinstance(value, str) and "~" in value:
            result[key] = os.path.expanduser(value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: dict) -> dict:
    """Apply environment variable overrides."""
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        config.setdefault("openrouter", {})["api_key"] = env_key

    env_backend = os.environ.get("LLM_BACKEND")
    if env_backend:
        config["backend"] = env_backend

    return config


def _get_default_config_path() -> str:
    """Get the default config file path relative to the project root."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "config", "default.yaml")


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from YAML file with env overrides.

    Args:
        config_path: Path to YAML config file. Uses config/default.yaml if None.

    Returns:
        Merged configuration dict.
    """
    path = config_path or _get_default_config_path()

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        config = yaml.safe_load(f) or {}

    # Load user overrides if they exist
    user_config_path = os.path.expanduser("~/.config/talking-llm/config.yaml")
    if os.path.exists(user_config_path):
        with open(user_config_path) as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)

    config = _apply_env_overrides(config)
    config = _expand_paths(config)

    return config


_VALID_BACKENDS = {"ollama", "openrouter", "auto"}
_VALID_WHISPER_MODELS = {"tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en", "large"}


def validate_config(config: dict) -> list[str]:
    """Validate configuration values. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []

    backend = config.get("backend", "ollama")
    if backend not in _VALID_BACKENDS:
        errors.append(f"Invalid backend '{backend}', must be one of {_VALID_BACKENDS}")

    whisper_model = config.get("whisper", {}).get("model", "base.en")
    if whisper_model not in _VALID_WHISPER_MODELS:
        errors.append(f"Invalid whisper model '{whisper_model}', must be one of {_VALID_WHISPER_MODELS}")

    if backend in ("openrouter", "auto"):
        api_key = config.get("openrouter", {}).get("api_key", "")
        if not api_key:
            errors.append("OpenRouter API key required when backend is 'openrouter' or 'auto'")

    ollama_cfg = config.get("ollama", {})
    if not isinstance(ollama_cfg.get("base_url", "http://localhost:11434"), str):
        errors.append("ollama.base_url must be a string")

    db_path = config.get("database", {}).get("path", "")
    if not isinstance(db_path, str) or not db_path:
        errors.append("database.path must be a non-empty string")

    return errors
