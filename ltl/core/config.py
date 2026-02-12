"""Configuration management for LTL."""

import os
import json
from pathlib import Path


LTL_DIR = os.path.expanduser("~/.ltl")
CONFIG_PATH = os.path.join(LTL_DIR, "config.json")


def get_config_path():
    """Get the configuration file path."""
    return CONFIG_PATH


def load_config():
    """Load configuration from file."""
    if not os.path.exists(CONFIG_PATH):
        return get_default_config()

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


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
