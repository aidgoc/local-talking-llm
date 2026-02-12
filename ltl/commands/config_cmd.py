"""Config command - Manage configuration."""

import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.config import load_config, get_config_path


def show(args):
    """Show current configuration."""
    config_path = get_config_path()

    if not os.path.exists(config_path):
        print("❌ No configuration found.")
        print(f"   Run: ltl init")
        return

    print("⚙️  Configuration\n")
    print(f"Path: {config_path}\n")
    print("=" * 60)

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        print(json.dumps(config, indent=2))
    except Exception as e:
        print(f"Error reading config: {e}")

    print("=" * 60)


def edit(args):
    """Edit configuration."""
    config_path = get_config_path()

    # Get default editor
    editor = os.environ.get("EDITOR", "nano")

    if not os.path.exists(config_path):
        print("❌ No configuration found.")
        print(f"   Run: ltl init")
        return

    print(f"📝 Opening config in {editor}...")
    os.system(f'{editor} "{config_path}"')
    print("\n✓ Config updated")
