"""Status command - Show system status."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.config import load_config, get_config_path
from ltl.core.workspace import get_workspace_path


def run(args):
    """Run the status command."""
    print("🎙️  LTL Status\n")
    print("=" * 60)

    # Config status
    config_path = get_config_path()
    if os.path.exists(config_path):
        print(f"✓ Config: {config_path}")
        try:
            cfg = load_config()
            print(f"  Model: {cfg.get('model', 'Not set')}")
            print(f"  Backend: {cfg.get('backend', 'ollama')}")
        except Exception as e:
            print(f"  ⚠️  Error loading config: {e}")
    else:
        print(f"✗ Config: {config_path}")
        print("  Run: ltl init")

    # Workspace status
    workspace_path = get_workspace_path()
    if os.path.exists(workspace_path):
        print(f"\n✓ Workspace: {workspace_path}")

        # Check for template files
        templates = ["AGENTS.md", "USER.md", "IDENTITY.md", "SOUL.md", "TOOLS.md"]
        for template in templates:
            template_path = os.path.join(workspace_path, template)
            if os.path.exists(template_path):
                print(f"  ✓ {template}")
            else:
                print(f"  ✗ {template}")

        # Check for MEMORY.md in memory subdirectory
        memory_path = os.path.join(workspace_path, "memory", "MEMORY.md")
        if os.path.exists(memory_path):
            print(f"  ✓ memory/MEMORY.md")
        else:
            print(f"  ✗ memory/MEMORY.md")
    else:
        print(f"\n✗ Workspace: {workspace_path}")
        print("  Run: ltl init")

    print("\n" + "=" * 60)

    # API Keys status
    try:
        cfg = load_config()
        providers = cfg.get("providers", {})

        print("\nAPI Providers:")
        providers_status = [
            ("OpenRouter", providers.get("openrouter", {}).get("api_key")),
            ("Anthropic", providers.get("anthropic", {}).get("api_key")),
            ("OpenAI", providers.get("openai", {}).get("api_key")),
            ("Groq", providers.get("groq", {}).get("api_key")),
        ]

        for name, key in providers_status:
            if key:
                print(f"  ✓ {name}: Configured")
            else:
                print(f"  ✗ {name}: Not set")
    except:
        pass

    print("\n" + "=" * 60)
