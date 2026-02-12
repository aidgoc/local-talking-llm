"""Interactive configuration wizard for LTL.

Provides OpenCode-style interactive configuration management.
"""

import os
import sys
import json
import getpass
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.config import load_config, save_config, get_config_path


class Colors:
    """Terminal colors for better UX."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{text}{Colors.END}")
    print("=" * len(text))


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.END}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.END}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def ask_question(prompt: str, default: str = "", password: bool = False) -> str:
    """Ask a question with optional default value."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "

    if password:
        value = getpass.getpass(full_prompt)
    else:
        value = input(full_prompt)

    return value if value else default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{prompt} [{default_str}]: ").strip().lower()

    if not response:
        return default
    return response in ["y", "yes"]


def ask_choice(prompt: str, choices: list, default: int = 0) -> int:
    """Ask user to choose from a list."""
    print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        marker = "→" if i - 1 == default else " "
        print(f"  {marker} {i}. {choice}")

    while True:
        try:
            response = input(f"\nSelect [1-{len(choices)}, default={default + 1}]: ").strip()
            if not response:
                return default
            choice = int(response) - 1
            if 0 <= choice < len(choices):
                return choice
            print_error(f"Please enter a number between 1 and {len(choices)}")
        except ValueError:
            print_error("Please enter a valid number")


class ConfigWizard:
    """Interactive configuration wizard for LTL."""

    def __init__(self):
        self.config = load_config()

    def run_full_setup(self):
        """Run complete setup wizard."""
        print_header("🎙️ LTL Configuration Wizard")
        print("\nThis wizard will help you configure your Local Talking LLM.")
        print("You can skip any section by pressing Enter to accept defaults.\n")

        # 1. Backend Configuration
        self.configure_backend()

        # 2. Provider Configuration
        self.configure_providers()

        # 3. Channel Configuration
        self.configure_channels()

        # 4. Tool Configuration
        self.configure_tools()

        # 5. Save Configuration
        self.save_config()

        print_header("✅ Setup Complete!")
        print("\nYou can now use LTL:")
        print("  ltl status          - Check system status")
        print("  ltl tool list       - List available tools")
        print("  ltl chat            - Start chatting\n")

    def configure_backend(self):
        """Configure backend settings."""
        print_header("Step 1: Backend Configuration")

        backends = ["ollama", "openrouter", "auto"]
        current = self.config.get("backend", "ollama")

        print_info(f"Current backend: {current}")
        choice = ask_choice(
            "Select your preferred backend:",
            ["Ollama (local, private)", "OpenRouter (cloud)", "Auto (switch based on connectivity)"],
            backends.index(current) if current in backends else 0,
        )

        self.config["backend"] = backends[choice]
        print_success(f"Backend set to: {backends[choice]}")

    def configure_providers(self):
        """Configure API providers."""
        print_header("Step 2: API Providers")

        # Ollama
        print_info("\n📦 Ollama (Local LLM)")
        if ask_yes_no("Configure Ollama?", True):
            ollama_config = self.config.get("providers", {}).get("ollama", {})
            base_url = ask_question("Ollama base URL", ollama_config.get("base_url", "http://localhost:11434"))
            text_model = ask_question("Text model", ollama_config.get("text_model", "gemma3"))

            if "providers" not in self.config:
                self.config["providers"] = {}
            self.config["providers"]["ollama"] = {
                "base_url": base_url,
                "text_model": text_model,
                "vision_model": ollama_config.get("vision_model", "moondream"),
            }
            print_success("Ollama configured")

        # OpenRouter
        print_info("\n🌐 OpenRouter (Cloud LLM)")
        if ask_yes_no("Configure OpenRouter?", False):
            api_key = ask_question("OpenRouter API key", password=True)
            if api_key:
                if "providers" not in self.config:
                    self.config["providers"] = {}
                self.config["providers"]["openrouter"] = {
                    "api_key": api_key,
                    "api_base": "https://openrouter.ai/api/v1",
                }
                print_success("OpenRouter configured")

        # LocalAI
        print_info("\n⚡ LocalAI (Enhanced Local LLM)")
        if ask_yes_no("Configure LocalAI?", False):
            if "providers" not in self.config:
                self.config["providers"] = {}
            self.config["providers"]["localai"] = {
                "enabled": True,
                "base_url": ask_question("LocalAI URL", "http://localhost:8080"),
            }
            print_success("LocalAI configured")

    def configure_channels(self):
        """Configure messaging channels."""
        print_header("Step 3: Messaging Channels (Optional)")

        # Telegram
        print_info("\n📱 Telegram Bot")
        if ask_yes_no("Set up Telegram bot?", False):
            print_info("Get your bot token from @BotFather on Telegram")
            token = ask_question("Bot token", password=True)
            user_id = ask_question("Your Telegram user ID (from @userinfobot)")

            if "channels" not in self.config:
                self.config["channels"] = {}
            self.config["channels"]["telegram"] = {
                "enabled": bool(token),
                "token": token,
                "allow_from": [user_id] if user_id else [],
            }
            print_success("Telegram configured")

        # Discord
        print_info("\n💬 Discord Bot")
        if ask_yes_no("Set up Discord bot?", False):
            print_info("Create a bot at https://discord.com/developers/applications")
            token = ask_question("Bot token", password=True)
            user_id = ask_question("Your Discord user ID")

            if "channels" not in self.config:
                self.config["channels"] = {}
            self.config["channels"]["discord"] = {
                "enabled": bool(token),
                "token": token,
                "allow_from": [user_id] if user_id else [],
            }
            print_success("Discord configured")

    def configure_tools(self):
        """Configure tool settings."""
        print_header("Step 4: Tool Configuration")

        # Web Search
        print_info("\n🔍 Web Search")
        max_results = ask_question("Default search results (1-10)", "5")
        if "tools" not in self.config:
            self.config["tools"] = {}
        if "web" not in self.config["tools"]:
            self.config["tools"]["web"] = {}
        self.config["tools"]["web"]["search"] = {
            "enabled": True,
            "max_results": int(max_results) if max_results.isdigit() else 5,
        }

        # Voice
        print_info("\n🎤 Voice Transcription")
        models = ["tiny", "base", "small", "medium"]
        choice = ask_choice(
            "Select Whisper model:",
            ["Tiny (fastest, 39MB)", "Base (balanced, 74MB)", "Small (better, 244MB)", "Medium (best, 769MB)"],
            1,
        )

        if "voice" not in self.config["tools"]:
            self.config["tools"]["voice"] = {}
        self.config["tools"]["voice"] = {"enabled": True, "transcription": "whisper", "whisper_model": models[choice]}
        print_success(f"Voice model set to: {models[choice]}")

    def save_config(self):
        """Save configuration to file."""
        try:
            save_config(self.config)
            print_success(f"Configuration saved to {get_config_path()}")
        except Exception as e:
            print_error(f"Failed to save configuration: {e}")

    def configure_single_setting(self, path: str, value: Any):
        """Configure a single setting by path (e.g., 'providers.openrouter.api_key')."""
        keys = path.split(".")
        config = self.config

        # Navigate to parent
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set value
        config[keys[-1]] = value
        save_config(self.config)
        print_success(f"Set {path} = {value if not isinstance(value, str) or len(value) < 20 else '***'}")


def set_provider(provider: str, api_key: Optional[str] = None, **kwargs):
    """Quick set a provider configuration."""
    config = load_config()

    if "providers" not in config:
        config["providers"] = {}

    if provider == "openrouter":
        config["providers"]["openrouter"] = {
            "api_key": api_key or "",
            "api_base": kwargs.get("base_url", "https://openrouter.ai/api/v1"),
        }
    elif provider == "ollama":
        config["providers"]["ollama"] = {
            "base_url": kwargs.get("base_url", "http://localhost:11434"),
            "text_model": kwargs.get("text_model", "gemma3"),
            "vision_model": kwargs.get("vision_model", "moondream"),
        }
    elif provider == "localai":
        config["providers"]["localai"] = {"enabled": True, "base_url": kwargs.get("base_url", "http://localhost:8080")}

    save_config(config)
    print_success(f"{provider} provider configured")


def set_channel(channel: str, token: str, user_id: str = ""):
    """Quick set a channel configuration."""
    config = load_config()

    if "channels" not in config:
        config["channels"] = {}

    config["channels"][channel] = {"enabled": bool(token), "token": token, "allow_from": [user_id] if user_id else []}

    save_config(config)
    print_success(f"{channel} channel configured")


def show_config():
    """Display current configuration in a formatted way."""
    config = load_config()

    print_header("Current LTL Configuration")

    # Backend
    print(f"\n{Colors.BOLD}Backend:{Colors.END}")
    print(f"  Current: {config.get('backend', 'ollama')}")

    # Providers
    print(f"\n{Colors.BOLD}Providers:{Colors.END}")
    providers = config.get("providers", {})
    for name, settings in providers.items():
        enabled = "✅" if settings.get("enabled") or settings.get("api_key") else "⚪"
        print(f"  {enabled} {name}")

    # Channels
    print(f"\n{Colors.BOLD}Channels:{Colors.END}")
    channels = config.get("channels", {})
    for name, settings in channels.items():
        enabled = "✅" if settings.get("enabled") and settings.get("token") else "⚪"
        print(f"  {enabled} {name}")

    # Tools
    print(f"\n{Colors.BOLD}Tools:{Colors.END}")
    tools = config.get("tools", {})
    if "web" in tools:
        print(f"  ✅ Web search (max: {tools['web'].get('search', {}).get('max_results', 5)} results)")
    if "voice" in tools:
        print(f"  ✅ Voice ({tools['voice'].get('whisper_model', 'base')})")

    print(f"\n{Colors.CYAN}Config file: {get_config_path()}{Colors.END}")


if __name__ == "__main__":
    wizard = ConfigWizard()
    wizard.run_full_setup()
