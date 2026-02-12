"""Tool command - Execute tools from CLI."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.tools import get_registry
from ltl.tools import register_builtin_tools


def run(args):
    """Run the tool command."""
    # Initialize registry with built-in tools
    registry = get_registry()
    register_builtin_tools(registry)

    if args.tool_command == "list":
        # List all available tools
        print(registry.get_all_help())
        return

    if args.tool_command == "help":
        # Show help for specific tool
        if not args.tool_name:
            print("Usage: ltl tool help <tool-name>")
            return
        help_text = registry.get_tool_help(args.tool_name)
        print(help_text)
        return

    # Execute a tool
    tool_name = args.tool_command
    tool = registry.get(tool_name)

    if not tool:
        print(f"❌ Tool not found: {tool_name}")
        print("\nAvailable tools:")
        for name in registry.list_tools():
            print(f"  - {name}")
        return

    # Parse remaining arguments as tool parameters
    tool_args = {}
    if args.tool_args:
        # Simple argument parsing: key=value pairs
        for arg in args.tool_args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                # Try to convert value to appropriate type
                try:
                    # Try integer
                    tool_args[key] = int(value)
                except ValueError:
                    try:
                        # Try float
                        tool_args[key] = float(value)
                    except ValueError:
                        # Try boolean
                        if value.lower() == "true":
                            tool_args[key] = True
                        elif value.lower() == "false":
                            tool_args[key] = False
                        else:
                            # Keep as string
                            tool_args[key] = value

    # Execute the tool
    print(f"🔧 Executing: {tool_name}")
    print(f"   Args: {tool_args}\n")

    result = registry.execute(tool_name, **tool_args)

    if result.success:
        print("✅ Success:")
        print(result.data)
    else:
        print("❌ Error:")
        print(result.error)
        if result.data:
            print("\nData:")
            print(result.data)
