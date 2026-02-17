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
from ltl.commands.gateway import start_background as start_gateway_background

# Optional TTS import
try:
    from tts import TextToSpeechService

    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class LTLTUI:
    """Unified Terminal User Interface for LTL."""

    def __init__(self):
        self.console = Console()
        self.config = load_config()
        self.chat_assistant = TextChatAssistant(self.config)
        self.running = False
        self.voice_enabled = False
        self.tts_enabled = False
        self.current_mode = "chat"
        self.chat_history: List[str] = []

        # Check for voice components
        self.voice_enabled = self._check_voice_components()
        self.tts_enabled = self._check_tts_components()

        # Auto-start gateway (Telegram, Discord) in background if configured
        self.active_channels = []
        try:
            self.active_channels = start_gateway_background(self.config)
            if self.active_channels:
                self.console.print(f"[green]✓ Gateway started: {', '.join(self.active_channels)}[/green]")
        except Exception as e:
            self.console.print(f"[yellow]⚠️  Gateway unavailable: {e}[/yellow]")

        # TTS will be initialized on-demand using subprocess

    def _check_voice_components(self) -> bool:
        """Check if voice components are available."""
        try:
            # Check if whisper venv exists and has packages
            whisper_venv = os.path.expanduser("~/whisper-env")
            if os.path.exists(whisper_venv):
                # Try to import from venv
                import sys
                import subprocess

                # Use the venv python to test imports
                venv_python = os.path.join(whisper_venv, "bin", "python3")
                if os.path.exists(venv_python):
                    result = subprocess.run(
                        [venv_python, "-c", "import whisper, sounddevice; print('OK')"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    return result.returncode == 0 and "OK" in result.stdout

            return False
        except Exception:
            return False

    def _check_tts_components(self) -> bool:
        """Check if TTS components are available."""
        try:
            # Check if voice model exists
            voice_path = os.path.expanduser("~/.local/share/piper/en_US-lessac-medium.onnx")
            if not os.path.exists(voice_path):
                return False

            # Try to test TTS in venv
            import subprocess

            venv_python = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                ".venv311",
                "bin",
                "python3",
            )

            if os.path.exists(venv_python):
                result = subprocess.run(
                    [
                        venv_python,
                        "-c",
                        """
import sys
sys.path.insert(0, '.')
try:
    from tts import TextToSpeechService
    tts = TextToSpeechService()
    sample_rate, audio = tts.synthesize('test')
    print('OK' if len(audio) > 0 else 'FAIL')
except Exception as e:
    print(f'ERROR: {e}')
""",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                )
                return result.returncode == 0 and "OK" in result.stdout

            return False
        except Exception as e:
            print(f"TTS check failed: {e}")
            return False
        except Exception:
            return False
        except Exception:
            return False

    def show_welcome(self):
        """Show welcome screen."""
        self.console.clear()
        title_panel = Panel(
            "🎙️ Welcome to LTL - Local Talking LLM\n\n"
            "Your privacy-first AI assistant with voice, vision, and tools.\n\n"
            f"Voice Input: {'✅ Enabled' if self.voice_enabled else '❌ Disabled'}\n"
            f"Voice Output: {'✅ Enabled' if self.tts_enabled else '❌ Disabled'}\n"
            f"Ollama: {'✅ Connected' if self._check_ollama() else '❌ Not connected'}\n"
            f"Telegram: {'✅ ' + ', '.join(self.active_channels) if self.active_channels else '❌ Not configured'}\n\n"
            "Commands:\n"
            "  /chat     - Text chat mode\n"
            "  /voice    - Voice input mode\n"
            "  /record   - Start voice recording\n"
            "  /speak    - Voice input mode\n"
            "  /tools    - Execute tools\n"
            "  /status   - System status\n"
            "  /gateway  - Channel gateway\n"
            "  /config   - Configuration\n"
            "  /clear    - Clear chat history\n"
            "  /help     - Show this help\n"
            "  /exit     - Exit LTL\n\n"
            "Just type your message to chat, or use /voice for speech!",
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
            self.handle_voice_command()
        elif cmd == "/record" or cmd == "/speak":
            self.handle_voice_input()
        elif cmd == "/tools":
            self.show_tools()
        elif cmd.startswith("/tool "):
            self.execute_tool_command(cmd)
        elif cmd == "/gateway":
            self.start_gateway()
        elif cmd == "/config":
            self.show_config()
        else:
            # Not a command, treat as chat message
            self.handle_chat(command)

        return False

    def handle_voice_command(self):
        """Handle voice mode command."""
        if self.voice_enabled:
            self.current_mode = "voice"
            self.console.print("[blue]🎤 Switched to voice mode[/blue]")
            self.console.print("[cyan]Commands:[/cyan]")
            self.console.print("  /record  - Start voice recording")
            self.console.print("  /speak   - Voice input mode")
            self.console.print("  /chat    - Back to text mode")
        else:
            self.console.print("[red]❌ Voice not available. Install whisper and sounddevice.[/red]")
            self.console.print("[yellow]Run: ltl setup whisper[/yellow]")

    def handle_voice_input(self):
        """Handle voice input recording."""
        if not self.voice_enabled:
            self.console.print("[red]❌ Voice not available[/red]")
            return

        import os

        try:
            # Use the whisper-env python for voice processing
            whisper_venv = os.path.expanduser("~/whisper-env")
            venv_python = os.path.join(whisper_venv, "bin", "python3")

            if not os.path.exists(venv_python):
                self.console.print("[red]❌ Whisper environment not found[/red]")
                return

            # Create a simple voice recording script
            voice_script = """
import sys
import numpy as np
import sounddevice as sd
import whisper
import time

print("🎤 Recording... Press Enter to stop", flush=True)

# Get device's native sample rate
import sounddevice as sd
try:
    device_info = sd.query_devices(sd.default.device[0], "input")
    samplerate = int(device_info["default_samplerate"])
    print(f"Using device sample rate: {samplerate} Hz", flush=True)
except:
    samplerate = 44100  # Common fallback
    print(f"Using fallback sample rate: {samplerate} Hz", flush=True)

duration = 10  # Max 10 seconds
recording = []

def callback(indata, frames, time_info, status):
    recording.append(indata.copy())

try:
    stream = sd.InputStream(samplerate=samplerate, channels=1, dtype="float32", callback=callback)
    with stream:
        input()  # Wait for Enter
        stream.stop()
except Exception as e:
    print(f"Recording failed: {e}", flush=True)
    sys.exit(1)

if recording:
    # Concatenate audio
    audio = np.concatenate(recording, axis=0).flatten()

    # Resample to 16kHz for Whisper if needed
    if samplerate != 16000:
        print(f"Resampling from {samplerate} Hz to 16000 Hz for Whisper...", flush=True)
        try:
            from scipy.signal import resample_poly
            from math import gcd
            factor = gcd(samplerate, 16000)
            up = 16000 // factor
            down = samplerate // factor
            audio = resample_poly(audio, up, down).astype(np.float32)
        except ImportError:
            # Fallback: simple linear interpolation if scipy not available
            print("scipy not available, using simple resampling...", flush=True)
            length_ratio = 16000 / samplerate
            new_length = int(len(audio) * length_ratio)
            indices = np.arange(new_length) / length_ratio
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    # Load and use whisper
    print("Transcribing...", flush=True)
    model = whisper.load_model("tiny")
    result = model.transcribe(audio, fp16=False)
    text = result["text"].strip()

    if text:
        print(f"TRANSCRIBED: {text}", flush=True)
    else:
        print("NO_SPEECH", flush=True)
else:
    print("NO_AUDIO", flush=True)
"""

            # Write script to temp file and execute
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(voice_script)
                script_path = f.name

            try:
                import subprocess

                self.console.print("[green]🎤 Recording... Press Enter to stop[/green]")

                # Run the voice script
                result = subprocess.run([venv_python, script_path], capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output.startswith("TRANSCRIBED: "):
                        text = output[12:]  # Remove "TRANSCRIBED: " prefix
                        self.console.print(f"[green]🎤 Heard: {text}[/green]")
                        # Process as chat message
                        self.handle_chat(text)
                    elif output == "NO_SPEECH":
                        self.console.print("[yellow]No speech detected[/yellow]")
                    elif output == "NO_AUDIO":
                        self.console.print("[yellow]No audio recorded[/yellow]")
                    else:
                        self.console.print(f"[yellow]Recording result: {output}[/yellow]")
                else:
                    self.console.print(f"[red]❌ Recording failed: {result.stderr}[/red]")

            finally:
                # Clean up temp file
                import os

                try:
                    os.unlink(script_path)
                except:
                    pass

        except Exception as e:
            self.console.print(f"[red]❌ Voice recording failed: {e}[/red]")
            self.console.print("[yellow]Make sure microphone is available[/yellow]")

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

        # Voice output if available
        if self.tts_enabled:
            try:
                with self.console.status("[magenta]Speaking...", spinner="dots"):
                    self._speak_text(response)
            except Exception as e:
                self.console.print(f"[yellow]Voice output failed: {e}[/yellow]")

    def _speak_text(self, text: str):
        """Speak text using TTS in venv."""
        try:
            import subprocess
            import tempfile
            import os

            # Create TTS script
            tts_script = f'''
import sys
sys.path.insert(0, '.')
from tts import TextToSpeechService
import sounddevice as sd

tts = TextToSpeechService()
sample_rate, audio = tts.long_form_synthesize("""{text.replace('"', '\\"')}""")
sd.play(audio, sample_rate)
sd.wait()
print("TTS_COMPLETE")
'''

            # Write script to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(tts_script)
                script_path = f.name

            try:
                # Run TTS in venv
                venv_python = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    ".venv311",
                    "bin",
                    "python3",
                )
                result = subprocess.run(
                    [venv_python, script_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                )

                if result.returncode != 0:
                    raise Exception(f"TTS failed: {result.stderr}")

            finally:
                # Clean up temp file
                try:
                    os.unlink(script_path)
                except:
                    pass

        except Exception as e:
            raise Exception(f"Voice output failed: {e}")

    def _play_audio(self, sample_rate: int, audio_array):
        """Play audio using sounddevice."""
        try:
            import sounddevice as sd

            sd.play(audio_array, sample_rate)
            sd.wait()
        except ImportError:
            self.console.print("[yellow]Audio playback not available[/yellow]")
        except Exception as e:
            self.console.print(f"[yellow]Audio playback failed: {e}[/yellow]")

    def show_tools(self):
        """Show available tools."""
        from ltl.core.tools import get_registry
        from ltl.tools import register_builtin_tools

        registry = get_registry()
        register_builtin_tools(registry)

        tools_panel = Panel(
            "Available Tools:\n\n"
            + "\n".join([f"  • {name}: {registry.get(name).description()}" for name in registry.list_tools()])
            + '\n\nTo execute a tool: /tool <name> [args]\nExample: /tool web_search query="python"',
            title="🔧 Tools",
            border_style="yellow",
        )
        self.console.print(tools_panel)

    def execute_tool_command(self, command: str):
        """Execute a tool command like /tool web_search query="test"."""
        try:
            parts = command.split()
            if len(parts) < 2:
                self.console.print("[red]Usage: /tool <tool_name> [args][/red]")
                return

            tool_name = parts[1]
            args = parts[2:] if len(parts) > 2 else []

            # Parse key=value args
            kwargs = {}
            for arg in args:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    # Try to convert to appropriate type
                    try:
                        if value.isdigit():
                            kwargs[key] = int(value)
                        elif value.lower() in ["true", "false"]:
                            kwargs[key] = value.lower() == "true"
                        else:
                            kwargs[key] = value
                    except:
                        kwargs[key] = value

            # Execute tool
            from ltl.core.tools import execute_tool

            result = execute_tool(tool_name, **kwargs)

            if result.success:
                result_panel = Panel(result.data, title=f"✅ {tool_name}", border_style="green")
            else:
                result_panel = Panel(result.error, title=f"❌ {tool_name}", border_style="red")

            self.console.print(result_panel)

        except Exception as e:
            self.console.print(f"[red]❌ Tool execution error: {e}[/red]")

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
