"""Enhanced config command with interactive wizard and CLI configuration."""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.wizard import (
    ConfigWizard,
    set_provider,
    set_channel,
    show_config,
    print_header,
    print_success,
    print_error,
    print_info,
)
from ltl.core.config import load_config, save_config, get_config_path


def run(args):
    """Run the enhanced config command."""
    if hasattr(args, "config_command") and args.config_command:
        if args.config_command == "wizard":
            # Run full interactive wizard
            wizard = ConfigWizard()
            wizard.run_full_setup()

        elif args.config_command == "show":
            # Show current config
            show_config()

        elif args.config_command == "set":
            # Set a specific value
            if not args.key:
                print_error("Missing --key argument")
                print_info("Usage: ltl config set --key <path> --value <value>")
                return

            wizard = ConfigWizard()
            wizard.configure_single_setting(args.key, args.value)

        elif args.config_command == "provider":
            # Configure a provider
            configure_provider_cli(args)

        elif args.config_command == "channel":
            # Configure a channel
            configure_channel_cli(args)

        elif args.config_command == "edit":
            # Open in editor
            edit_config()

        else:
            print_error(f"Unknown config command: {args.config_command}")
            print_info("Run 'ltl config --help' for available commands")
    else:
        # Default: show config
        show_config()


def configure_provider_cli(args):
    """Configure provider via CLI arguments."""
    if not args.name:
        print_error("Provider name required")
        print_info("Usage: ltl config provider <name> --api-key <key>")
        return

    provider_name = args.name.lower()

    if provider_name == "openrouter":
        api_key = args.api_key or input("OpenRouter API key: ")
        set_provider("openrouter", api_key=api_key)

    elif provider_name == "ollama":
        base_url = args.base_url or "http://localhost:11434"
        text_model = args.text_model or "gemma3"
        set_provider("ollama", base_url=base_url, text_model=text_model)

    elif provider_name == "localai":
        base_url = args.base_url or "http://localhost:8080"
        set_provider("localai", base_url=base_url)

    else:
        print_error(f"Unknown provider: {provider_name}")
        print_info("Available providers: openrouter, ollama, localai")


def configure_channel_cli(args):
    """Configure channel via CLI arguments."""
    if not args.name:
        print_error("Channel name required")
        print_info("Usage: ltl config channel <name> --token <token>")
        return

    channel_name = args.name.lower()

    if channel_name not in ["telegram", "discord"]:
        print_error(f"Unknown channel: {channel_name}")
        print_info("Available channels: telegram, discord")
        return

    token = args.token
    if not token:
        token = input(f"{channel_name.title()} bot token: ")

    user_id = args.user_id or input("Your user ID (optional): ")

    set_channel(channel_name, token, user_id)


def edit_config():
    """Open config in default editor."""
    import subprocess

    config_path = get_config_path()
    editor = os.environ.get("EDITOR", "nano")

    print_info(f"Opening {config_path} in {editor}...")
    subprocess.call([editor, config_path])
    print_success("Config updated")


# Add argument parser for config subcommands
def add_config_subparser(subparsers):
    """Add config subparser with all options."""
    config_parser = subparsers.add_parser(
        "config",
        help="Manage configuration (interactive wizard, show, set values)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ltl config                    Show current configuration
  ltl config wizard             Run interactive setup wizard
  ltl config show               Display current settings
  ltl config edit               Edit configuration file
  
  # Set specific values
  ltl config set --key providers.openrouter.api_key --value "sk-..."
  ltl config set --key backend --value "openrouter"
  
  # Configure providers
  ltl config provider openrouter --api-key "sk-..."
  ltl config provider ollama --base-url http://localhost:11434
  ltl config provider localai --base-url http://localhost:8080
  
  # Configure channels
  ltl config channel telegram --token "YOUR_BOT_TOKEN" --user-id "123456"
  ltl config channel discord --token "YOUR_BOT_TOKEN" --user-id "123456"
        """,
    )

    config_parser.add_argument(
        "config_command",
        nargs="?",
        choices=["wizard", "show", "set", "edit", "provider", "channel"],
        help="Config subcommand",
    )

    # For 'set' command
    config_parser.add_argument("--key", "-k", help="Configuration key path (e.g., providers.openrouter.api_key)")
    config_parser.add_argument("--value", "-v", help="Value to set")

    # For 'provider' command
    config_parser.add_argument("name", nargs="?", help="Provider name (openrouter, ollama, localai)")
    config_parser.add_argument("--api-key", help="API key for the provider")
    config_parser.add_argument("--base-url", help="Base URL for the provider")
    config_parser.add_argument("--text-model", help="Text model name (for Ollama)")

    # For 'channel' command
    config_parser.add_argument("--token", help="Bot token")
    config_parser.add_argument("--user-id", help="Authorized user ID")

    config_parser.set_defaults(func=run)


if __name__ == "__main__":
    # Test the wizard
    wizard = ConfigWizard()
    wizard.run_full_setup()
