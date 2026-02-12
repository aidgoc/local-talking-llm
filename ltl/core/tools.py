"""Tool registry and base classes for LTL.

Inspired by PicoClaw's tool system - clean, modular, extensible.
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None


class Tool(ABC):
    """Base class for all tools.

    All tools must implement:
    - name(): Return the tool name
    - description(): Return the tool description
    - parameters(): Return parameter definitions
    - execute(): Execute the tool with given arguments
    """

    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""
        pass

    @abstractmethod
    def description(self) -> str:
        """Return the tool description."""
        pass

    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """Return parameter definitions."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for this tool (for LLM function calling)."""
        params = self.parameters()
        properties = {}
        required = []

        for param in params:
            properties[param.name] = {"type": param.type, "description": param.description}
            if param.required:
                required.append(param.name)

        return {
            "name": self.name(),
            "description": self.description(),
            "parameters": {"type": "object", "properties": properties, "required": required},
        }

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments against parameter definitions."""
        params = {p.name: p for p in self.parameters()}

        # Check required parameters
        for name, param in params.items():
            if param.required and name not in args:
                return False, f"Missing required parameter: {name}"

        # Check for unknown parameters
        for name in args.keys():
            if name not in params:
                return False, f"Unknown parameter: {name}"

        return True, None


class ToolRegistry:
    """Central registry for all tools.

    Similar to PicoClaw's ToolRegistry - manages tool registration,
    discovery, and execution.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name()] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, data=None, error=f"Tool not found: {name}")

        # Validate arguments
        valid, error = tool.validate_args(kwargs)
        if not valid:
            return ToolResult(success=False, data=None, error=error)

        # Execute the tool
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Execution error: {str(e)}")

    def get_tool_help(self, name: str) -> str:
        """Get help text for a tool."""
        tool = self.get(name)
        if not tool:
            return f"Tool not found: {name}"

        lines = [
            f"\n{tool.name()}",
            "=" * len(tool.name()),
            f"\n{tool.description()}",
            "\nParameters:",
        ]

        for param in tool.parameters():
            req = "(required)" if param.required else "(optional)"
            default = f" [default: {param.default}]" if param.default is not None else ""
            lines.append(f"  --{param.name} <{param.type}> {req}{default}")
            lines.append(f"    {param.description}")

        return "\n".join(lines)

    def get_all_help(self) -> str:
        """Get help text for all tools."""
        lines = ["\nAvailable Tools:", "=" * 40, ""]

        for name in sorted(self.list_tools()):
            tool = self.get(name)
            if tool:  # Check if tool exists
                lines.append(f"\n{tool.name()}")
                lines.append(f"  {tool.description()}")
                lines.append(f"  Usage: ltl tool {tool.name()} [args]")

        return "\n".join(lines)


# Global registry instance
_registry = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(tool: Tool) -> None:
    """Register a tool in the global registry."""
    get_registry().register(tool)


def list_tools() -> List[str]:
    """List all registered tools."""
    return get_registry().list_tools()


def execute_tool(name: str, **kwargs) -> ToolResult:
    """Execute a tool by name."""
    return get_registry().execute(name, **kwargs)
