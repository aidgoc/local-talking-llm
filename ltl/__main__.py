#!/usr/bin/env python3
"""LTL - Local Talking LLM CLI

A PicoClaw-inspired CLI for the Local Talking LLM assistant.
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ltl.commands import init, status, chat, cron, config_cmd, tool, gateway, setup
from ltl.core.workspace import get_workspace_path
from ltl.core.config import load_config


def main():
    parser = argparse.ArgumentParser(
        prog="ltl",
        description="Local Talking LLM - Personal AI Assistant CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ltl init              Initialize workspace and configuration
  ltl status            Show system status
  ltl chat              Start interactive chat mode
  ltl chat -m "Hello"   Send single message
  ltl cron list         List scheduled tasks
  ltl config show       Show current configuration
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize workspace and configuration")
    init_parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing config")
    init_parser.set_defaults(func=init.run)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.set_defaults(func=status.run)

    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Chat with the assistant")
    chat_parser.add_argument("-m", "--message", help="Send a single message")
    chat_parser.add_argument("--backend", choices=["ollama", "openrouter", "auto"], help="Override backend")
    chat_parser.set_defaults(func=chat.run)

    # Cron command
    cron_parser = subparsers.add_parser("cron", help="Manage scheduled tasks")
    cron_subparsers = cron_parser.add_subparsers(dest="cron_command", help="Cron subcommands")

    cron_list = cron_subparsers.add_parser("list", help="List scheduled tasks")
    cron_list.set_defaults(func=cron.list_tasks)

    cron_add = cron_subparsers.add_parser("add", help="Add a scheduled task")
    cron_add.add_argument("-n", "--name", required=True, help="Task name")
    cron_add.add_argument("-m", "--message", required=True, help="Message to send")
    cron_add.add_argument("-e", "--every", type=int, help="Repeat every N seconds")
    cron_add.add_argument("--at", type=int, help="Run at specific time (Unix timestamp)")
    cron_add.set_defaults(func=cron.add_task)

    cron_remove = cron_subparsers.add_parser("remove", help="Remove a scheduled task")
    cron_remove.add_argument("task_id", help="Task ID to remove")
    cron_remove.set_defaults(func=cron.remove_task)

    # Tool command
    tool_parser = subparsers.add_parser("tool", help="Execute tools directly")
    tool_parser.add_argument("tool_command", help='Tool to execute or "list" to see all tools')
    tool_parser.add_argument("tool_args", nargs="*", help="Tool arguments (key=value pairs)")
    tool_parser.add_argument("--tool-name", help="Tool name for help command")
    tool_parser.set_defaults(func=tool.run)

    # Gateway command
    gateway_parser = subparsers.add_parser("gateway", help="Start the message gateway for channels")
    gateway_parser.set_defaults(func=gateway.run)

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up local services (LocalAI, Whisper, etc.)")
    setup_parser.add_argument("setup_command", nargs="?", help="Setup command (localai, whisper)")
    setup_parser.set_defaults(func=setup.run)

    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Config subcommands")

    config_show = config_subparsers.add_parser("show", help="Show current configuration")
    config_show.set_defaults(func=config_cmd.show)

    config_edit = config_subparsers.add_parser("edit", help="Edit configuration")
    config_edit.set_defaults(func=config_cmd.edit)

    # Parse args
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        # Run the command
        if hasattr(args, "func"):
            args.func(args)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
