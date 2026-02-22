"""Configuration management for LTL."""

import os
import json
from pathlib import Path


LTL_DIR = os.path.expanduser("~/.ltl")
CONFIG_PATH = os.path.join(LTL_DIR, "config.json")
ENV_PATH = os.path.join(LTL_DIR, ".env")

# Mapping of .env variable names to config paths
_ENV_MAP = {
    "OPENROUTER_API_KEY": ("providers", "openrouter", "api_key"),
    "ANTHROPIC_API_KEY":  ("providers", "anthropic", "api_key"),
    "OPENAI_API_KEY":     ("providers", "openai", "api_key"),
    "GROQ_API_KEY":       ("providers", "groq", "api_key"),
    "TELEGRAM_BOT_TOKEN": ("channels", "telegram", "token"),
}


def _load_env_overrides(config: dict) -> dict:
    """Load API keys from ~/.ltl/.env and overlay onto config."""
    env_vars = {}

    # Load from .env file if it exists
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    env_vars[key.strip()] = val.strip().strip('"').strip("'")

    # Also check actual environment variables (these take priority)
    for key in _ENV_MAP:
        if key in os.environ:
            env_vars[key] = os.environ[key]

    # Apply to config
    for env_key, path in _ENV_MAP.items():
        val = env_vars.get(env_key)
        if val:
            node = config
            for part in path[:-1]:
                node = node.setdefault(part, {})
            node[path[-1]] = val

    return config


def get_config_path():
    """Get the configuration file path."""
    return CONFIG_PATH


def load_config():
    """Load configuration from file, overlaying keys from ~/.ltl/.env."""
    if not os.path.exists(CONFIG_PATH):
        config = get_default_config()
    else:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

    return _load_env_overrides(config)


def save_config(config):
    """Save configuration to file."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def create_default_config():
    """Create default configuration file."""
    config = get_default_config()
    save_config(config)
    return config


def get_default_config():
    """Get default configuration."""
    return {
        "version": "2.1.0",
        "agents": {
            "defaults": {
                "workspace": "~/.ltl/workspace",
                "model": "gemma3",
                "max_tokens": 8192,
                "temperature": 0.7,
                "max_tool_iterations": 20,
            }
        },
        "backend": "ollama",
        "channels": {
            "telegram": {"enabled": False, "token": "", "allow_from": []},
            "discord": {"enabled": False, "token": "", "allow_from": []},
        },
        "providers": {
            "ollama": {"base_url": "http://localhost:11434", "text_model": "gemma3", "vision_model": "moondream"},
            "localai": {"enabled": False, "base_url": "http://localhost:8080"},
            "openrouter": {"api_key": "", "api_base": "https://openrouter.ai/api/v1"},
            "anthropic": {"api_key": "", "api_base": ""},
            "openai": {"api_key": "", "api_base": ""},
            "groq": {"api_key": "", "api_base": ""},
        },
        "tools": {
            "web": {"search": {"enabled": True, "max_results": 5}},
            "voice": {"enabled": True, "whisper_model": "base.en", "piper_voice": "en_US-lessac-medium"},
            "vision": {"enabled": True, "model": "moondream"},
        },
        "gateway": {"host": "0.0.0.0", "port": 18790},
    }
