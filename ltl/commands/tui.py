"""TUI command - Unified terminal interface for LTL."""

import os
import sys
import asyncio
import threading
import time
import select
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.columns import Columns
from rich.layout import Layout
from rich.table import Table
from rich.markdown import Markdown

from ltl.core.config import load_config
from ltl.commands.chat import TextChatAssistant


class LTLTUI:
    """Unified Terminal User Interface for LTL."""

    def __init__(self):
        self.console = Console()
        self.config = load_config()
        self.chat_assistant = TextChatAssistant(self.config)
        self.running = False
        self.voice_enabled = False
        self.current_mode = "chat"
        self.chat_history: List[str] = []

        # Check for voice components
        try:
            import whisper
            import sounddevice as sd

            self.voice_enabled = True
        except ImportError:
            self.voice_enabled = False

    def show_welcome(self):
        """Show welcome screen."""
        self.console.clear()
        title_panel = Panel(
            "🎙️ Welcome to LTL - Local Talking LLM\n\n"
            "Your privacy-first AI assistant with voice, vision, and tools.\n\n"
            f"Voice: {'✅ Enabled' if self.voice_enabled else '❌ Disabled'}\n"
            f"Ollama: {'✅ Connected' if self._check_ollama() else '❌ Not connected'}\n"
            f"Channels: {self._get_channel_status()}\n\n"
            "Commands:\n"
            "  /chat     - Text chat mode\n"
            "  /voice    - Voice input mode\n"
            "  /tools    - Execute tools\n"
            "  /status   - System status\n"
            "  /gateway  - Channel gateway\n"
            "  /config   - Configuration\n"
            "  /clear    - Clear chat history\n"
            "  /help     - Show this help\n"
            "  /exit     - Exit LTL\n\n"
            "Just type your message to chat!",
            title="LTL Assistant",
            border_style="blue",
        )
        self.console.print(title_panel)

    def show_status(self):
        """Show system status."""
        status_panel = Panel(
            f"🎙️ LTL Status\n\n"
            f"Mode: {self.current_mode.upper()}\n"
            f"Voice: {'✅' if self.voice_enabled else '❌'}\n"
            f"Ollama: {'✅' if self._check_ollama() else '❌'}\n"
            f"Channels: {self._get_channel_status()}\n"
            f"Chat History: {len(self.chat_history)} messages\n\n"
            f"Config: {self.config.get('version', 'unknown')}",
            title="System Status",
            border_style="green",
        )
        self.console.print(status_panel)

    def handle_command(self, command: str) -> bool:
        """Handle special commands. Returns True if should exit."""
        cmd = command.lower().strip()

        if cmd == "/exit" or cmd == "/quit":
            return True
        elif cmd == "/clear":
            self.chat_history.clear()
            self.chat_assistant.chat_history.clear()
            self.console.print("[green]🧹 Chat history cleared[/green]")
        elif cmd == "/status":
            self.show_status()
        elif cmd == "/help":
            self.show_welcome()
        elif cmd == "/chat":
            self.current_mode = "chat"
            self.console.print("[blue]📝 Switched to text chat mode[/blue]")
        elif cmd == "/voice":
            if self.voice_enabled:
                self.current_mode = "voice"
                self.console.print("[blue]🎤 Switched to voice mode[/blue]")
                self.console.print("[yellow]Voice mode not fully implemented yet. Use text chat.[/yellow]")
            else:
                self.console.print("[red]❌ Voice not available. Install whisper and sounddevice.[/red]")
        elif cmd == "/tools":
            self.show_tools()
        elif cmd == "/gateway":
            self.start_gateway()
        elif cmd == "/config":
            self.show_config()
        else:
            # Not a command, treat as chat message
            self.handle_chat(command)

        return False

    def handle_chat(self, message: str):
        """Handle chat message."""
        # Add to history
        self.chat_history.append(f"You: {message}")

        # Show thinking indicator
        with self.console.status("[green]Thinking...", spinner="dots"):
            response = self.chat_assistant.chat(message)

        # Add response to history
        self.chat_history.append(f"LTL: {response}")

        # Display response
        response_panel = Panel(response, title="🤖 LTL", border_style="green")
        self.console.print(response_panel)

    def show_tools(self):
        """Show available tools."""
        from ltl.core.tools import get_registry
        from ltl.tools import register_builtin_tools

        registry = get_registry()
        register_builtin_tools(registry)

        tools_panel = Panel(
            "Available Tools:\n\n"
            + "\n".join([f"  • {name}: {registry.get(name).description()}" for name in registry.list_tools()]),
            title="🔧 Tools",
            border_style="yellow",
        )
        self.console.print(tools_panel)

    def start_gateway(self):
        """Start the gateway."""
        try:
            from ltl.commands.gateway import run as gateway_run
            import argparse

            args = argparse.Namespace()
            self.console.print("[blue]🚀 Starting gateway...[/blue]")
            gateway_run(args)
        except Exception as e:
            self.console.print(f"[red]❌ Gateway error: {e}[/red]")

    def show_config(self):
        """Show configuration."""
        from ltl.commands.config_wizard import show_config

        show_config()

    def _check_ollama(self) -> bool:
        """Check if Ollama is running."""
        try:
            import requests

            ollama_config = self.config.get("providers", {}).get("ollama", {})
            base_url = ollama_config.get("base_url", "http://localhost:11434")
            response = requests.get(f"{base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False

    def _get_channel_status(self) -> str:
        """Get channel status."""
        channels = self.config.get("channels", {})
        enabled = []
        if channels.get("telegram", {}).get("enabled"):
            enabled.append("TG")
        if channels.get("discord", {}).get("enabled"):
            enabled.append("DC")
        return ", ".join(enabled) if enabled else "None"

    def run(self):
        """Run the TUI."""
        self.running = True
        self.show_welcome()

        try:
            while self.running:
                # Get user input
                try:
                    user_input = input("\n🎙️ You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_input:
                    continue

                # Handle commands or chat
                if user_input.startswith("/"):
                    if self.handle_command(user_input):
                        break
                else:
                    self.handle_chat(user_input)

        except KeyboardInterrupt:
            pass

        self.console.print("\n👋 Goodbye! Thanks for using LTL.")


def run(args):
    """Run the TUI command."""
    try:
        tui = LTLTUI()
        tui.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ TUI error: {e}")
        print("Falling back to text chat...")
        # Fallback to text chat
        from ltl.commands.chat import run as chat_run

        chat_run(args)
