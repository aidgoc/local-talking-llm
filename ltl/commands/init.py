"""Init command - Initialize workspace and configuration."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.workspace import create_workspace, get_workspace_path
from ltl.core.config import create_default_config, get_config_path


def run(args):
    """Run the init command."""
    print("🎙️  Initializing Local Talking LLM...\n")

    # Check if config already exists
    config_path = get_config_path()
    if os.path.exists(config_path) and not args.force:
        print(f"⚠️  Config already exists at {config_path}")
        response = input("Overwrite? (y/n): ").strip().lower()
        if response != "y":
            print("Aborted.")
            return
        print()

    # Create config
    print("📄 Creating configuration...")
    create_default_config()
    print(f"   ✓ Config: {config_path}")

    # Create workspace
    print("\n📁 Creating workspace...")
    create_workspace()
    workspace_path = get_workspace_path()
    print(f"   ✓ Workspace: {workspace_path}")

    print("\n" + "=" * 60)
    print("✅ LTL is ready!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Edit config:", config_path)
    print("     Add your API keys (OpenRouter, etc.)")
    print("  2. Start chatting: ltl chat")
    print("  3. Check status: ltl status")
    print("\n📖 Documentation: https://github.com/aidgoc/LTL")
    print("=" * 60)
