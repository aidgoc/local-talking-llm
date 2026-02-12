"""LocalAI provider for enhanced local LLM inference.

LocalAI is an open-source drop-in replacement for OpenAI API that runs locally.
Provides better performance and more control than Ollama for complex tasks.
"""

import os
import sys
import json
import requests
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.config import load_config


class LocalAIProvider:
    """LocalAI provider for local LLM inference."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.timeout = 120  # Longer timeout for local inference

    def chat_completion(
        self, messages: list, model: str = "gpt-3.5-turbo", temperature: float = 0.7, max_tokens: int = 1024
    ) -> Dict[str, Any]:
        """Make a chat completion request to LocalAI."""
        url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"LocalAI request failed: {e}")

    def list_models(self) -> list:
        """List available models in LocalAI."""
        url = f"{self.base_url}/v1/models"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return [model["id"] for model in data.get("data", [])]
        except requests.exceptions.RequestException:
            return []

    def is_available(self) -> bool:
        """Check if LocalAI is running and accessible."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False


def create_localai_provider(config: dict) -> Optional[LocalAIProvider]:
    """Create LocalAI provider from config."""
    localai_config = config.get("providers", {}).get("localai", {})

    if not localai_config.get("enabled", False):
        return None

    base_url = localai_config.get("base_url", "http://localhost:8080")

    provider = LocalAIProvider(base_url)

    if not provider.is_available():
        print(f"⚠️ LocalAI not available at {base_url}")
        return None

    print(f"✅ LocalAI connected at {base_url}")
    return provider


def get_localai_response(message: str, config: dict = None) -> Optional[str]:
    """Get response from LocalAI for a simple message."""
    if config is None:
        try:
            config = load_config()
        except:
            return None

    provider = create_localai_provider(config)
    if not provider:
        return None

    model = config.get("agents", {}).get("defaults", {}).get("model", "gpt-3.5-turbo")

    messages = [{"role": "system", "content": "You are a helpful AI assistant."}, {"role": "user", "content": message}]

    try:
        response = provider.chat_completion(messages, model=model)
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ LocalAI error: {e}")
        return None


# Integration with existing LTL providers
def update_config_for_localai():
    """Update config to include LocalAI provider."""
    try:
        config = load_config()

        if "providers" not in config:
            config["providers"] = {}

        if "localai" not in config["providers"]:
            config["providers"]["localai"] = {"enabled": False, "base_url": "http://localhost:8080"}

        # Save updated config
        from ltl.core.config import save_config

        save_config(config)

        print("✅ LocalAI provider added to config")
        print("   Edit ~/.ltl/config.json to enable and configure")

    except Exception as e:
        print(f"❌ Failed to update config: {e}")


if __name__ == "__main__":
    # Test LocalAI connection
    provider = LocalAIProvider()
    if provider.is_available():
        print("✅ LocalAI is running")
        models = provider.list_models()
        print(f"Available models: {models}")

        # Test simple response
        response = get_localai_response("Hello, what can you do?")
        if response:
            print(f"Response: {response[:200]}...")
    else:
        print("❌ LocalAI not running")
        print("Install LocalAI: https://localai.io/")
        print("Or run: docker run -p 8080:8080 localai/localai:latest")
