"""Setup command - Help users set up LocalAI and other local services."""

import os
import sys
import subprocess
import platform

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.config import load_config, save_config
from ltl.core.localai import update_config_for_localai
from ltl.core.whisper import setup_channel_transcription


def run(args):
    """Run the setup command."""
    print("🔧 LTL Setup Assistant\n")
    print("=" * 60)

    if hasattr(args, "setup_command") and args.setup_command:
        if args.setup_command == "localai":
            setup_localai()
        elif args.setup_command == "whisper":
            setup_whisper()
        else:
            print(f"Unknown setup command: {args.setup_command}")
    else:
        show_setup_menu()


def show_setup_menu():
    """Show the setup menu."""
    print("Available setup options:")
    print("  localai    Set up LocalAI for enhanced local LLM inference")
    print("  whisper    Set up open-source voice transcription")
    print("\nUsage: ltl setup <command>")
    print("\nExample: ltl setup localai")


def setup_localai():
    """Set up LocalAI for local LLM inference."""
    print("🚀 Setting up LocalAI\n")
    print("LocalAI provides OpenAI-compatible API locally.")
    print("It's faster and more capable than Ollama for complex tasks.\n")

    # Check if Docker is available
    docker_available = check_command("docker")

    if docker_available:
        print("✅ Docker found - recommended setup method")
        print("\nTo install LocalAI with Docker:")
        print("  docker run -p 8080:8080 -v $HOME/.localai:/models localai/localai:latest")
        print("\nOr with GPU support:")
        print("  docker run --gpus all -p 8080:8080 -v $HOME/.localai:/models localai/localai:latest-gpu")
        print("\nThen download models:")
        print(
            "  curl -X POST http://localhost:8080/models/apply -H 'Content-Type: application/json' -d '{\"url\": \"github:go-skynet/model-gallery/gpt4all-j.yaml\"}'"
        )

        response = input("\nWould you like me to run the Docker command? (y/n): ").strip().lower()
        if response == "y":
            run_docker_localai()

    else:
        print("⚠️ Docker not found - manual installation required")
        print("\nVisit: https://localai.io/")
        print("Or install Docker first: https://docs.docker.com/get-docker/")

    # Update config
    print("\n📄 Updating LTL configuration...")
    update_config_for_localai()

    print("\n✅ LocalAI setup complete!")
    print("Edit ~/.ltl/config.json to enable LocalAI:")
    print('  "providers": {"localai": {"enabled": true}}')


def setup_whisper():
    """Set up open-source voice transcription."""
    print("🎤 Setting up Whisper for voice transcription\n")
    print("Whisper is open-source speech recognition from OpenAI.\n")

    # Check if whisper is already available
    try:
        import openai_whisper

        print("✅ openai-whisper already installed")
    except ImportError:
        print("📦 Installing openai-whisper...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openai-whisper"])
            print("✅ openai-whisper installed successfully")
        except subprocess.CalledProcessError:
            print("❌ Failed to install openai-whisper")
            print("Try: pip install openai-whisper")
            return

    # Test whisper
    print("\n🧪 Testing Whisper...")
    try:
        from ltl.core.whisper import WhisperTranscriber

        transcriber = WhisperTranscriber("tiny")
        transcriber.load_model()
        print("✅ Whisper working - loaded tiny model")
        print("   For better accuracy, use 'base' or 'small' models")
    except Exception as e:
        print(f"❌ Whisper test failed: {e}")
        return

    # Update config
    print("\n📄 Updating LTL configuration...")
    setup_channel_transcription()
    print("✅ Whisper configured in LTL")


def run_docker_localai():
    """Run LocalAI with Docker."""
    print("\n🐳 Starting LocalAI with Docker...")

    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        "ltl-localai",
        "-p",
        "8080:8080",
        "-v",
        f"{os.path.expanduser('~/.localai')}:/models",
        "localai/localai:latest",
    ]

    try:
        subprocess.check_call(cmd)
        print("✅ LocalAI container started")
        print("   It may take a few minutes to download models on first run")
        print("   Check status: docker logs ltl-localai")
        print("   Stop: docker stop ltl-localai")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start LocalAI: {e}")
        print("Try running the command manually")


def check_command(cmd):
    """Check if a command is available."""
    try:
        subprocess.check_call([cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
