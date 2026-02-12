"""Built-in tools for LTL.

Open source and free tools for the assistant.
"""

import os
import time
import subprocess
import urllib.request
import urllib.parse
from typing import List
from html.parser import HTMLParser

from ltl.core.tools import Tool, ToolParameter, ToolResult


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo (free, no API key)."""

    def name(self) -> str:
        return "web_search"

    def description(self) -> str:
        return "Search the web for current information. Uses DuckDuckGo (free, no API key required). Returns titles, URLs, and snippets."

    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="query", type="string", description="Search query", required=True),
            ToolParameter(
                name="max_results", type="integer", description="Number of results (1-10)", required=False, default=5
            ),
        ]

    def execute(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            # Use DuckDuckGo HTML search
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8")

            # Parse results
            results = self._parse_results(html, min(max_results, 10))

            if not results:
                return ToolResult(success=True, data=f"No results found for: {query}")

            # Format results
            lines = [f"Results for: {query}\n"]
            for i, result in enumerate(results, 1):
                lines.append(f"{i}. {result['title']}")
                lines.append(f"   URL: {result['url']}")
                if result.get("snippet"):
                    lines.append(f"   {result['snippet'][:200]}...")
                lines.append("")

            return ToolResult(success=True, data="\n".join(lines))

        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Search failed: {str(e)}")

    def _parse_results(self, html: str, max_results: int) -> List[dict]:
        """Parse DuckDuckGo HTML results."""
        results = []

        # Simple parsing - look for result links
        import re

        # Find result blocks
        result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        matches = re.findall(result_pattern, html, re.DOTALL)

        for i, (url, title_html) in enumerate(matches[:max_results]):
            # Clean up title (remove HTML tags)
            title = re.sub(r"<[^>]+>", "", title_html)
            title = title.replace("&quot;", '"').replace("&amp;", "&")

            # Extract snippet (simplified)
            results.append({"title": title.strip(), "url": url, "snippet": ""})

        return results


class WebFetchTool(Tool):
    """Fetch and extract text content from a URL."""

    def name(self) -> str:
        return "web_fetch"

    def description(self) -> str:
        return "Fetch and extract text content from a URL. Useful for reading articles or documentation."

    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="url", type="string", description="URL to fetch", required=True),
            ToolParameter(
                name="max_chars",
                type="integer",
                description="Maximum characters to return",
                required=False,
                default=5000,
            ),
        ]

    def execute(self, url: str, max_chars: int = 5000) -> ToolResult:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8", errors="ignore")

            # Extract text
            text = self._extract_text(html)

            # Truncate if needed
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n\n[Content truncated. Total length: {len(text)} chars]"

            return ToolResult(success=True, data=text)

        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Fetch failed: {str(e)}")

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML."""
        import re
        import html as html_module

        # Remove scripts and styles
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)

        # Convert common block elements to newlines
        html = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", html)
        html = re.sub(r"<br\s*/?>", "\n", html)

        # Remove remaining HTML tags
        text = re.sub(r"<[^>]+>", "", html)

        # Decode HTML entities
        text = html_module.unescape(text)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]

        return "\n".join(lines)


class ReadFileTool(Tool):
    """Read contents of a file."""

    def name(self) -> str:
        return "read_file"

    def description(self) -> str:
        return "Read the contents of a file."

    def parameters(self) -> List[ToolParameter]:
        return [ToolParameter(name="path", type="string", description="Path to the file", required=True)]

    def execute(self, path: str) -> ToolResult:
        try:
            # Expand home directory
            path = os.path.expanduser(path)

            if not os.path.exists(path):
                return ToolResult(success=False, data=None, error=f"File not found: {path}")

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            return ToolResult(success=True, data=content)

        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Read failed: {str(e)}")


class WriteFileTool(Tool):
    """Write content to a file."""

    def name(self) -> str:
        return "write_file"

    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist."

    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="Path to the file", required=True),
            ToolParameter(name="content", type="string", description="Content to write", required=True),
            ToolParameter(
                name="append",
                type="boolean",
                description="Append to file instead of overwriting",
                required=False,
                default=False,
            ),
        ]

    def execute(self, path: str, content: str, append: bool = False) -> ToolResult:
        try:
            # Expand home directory
            path = os.path.expanduser(path)

            # Create directory if needed
            os.makedirs(os.path.dirname(path), exist_ok=True)

            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)

            action = "appended to" if append else "written to"
            return ToolResult(success=True, data=f"Content {action} {path}")

        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Write failed: {str(e)}")


class ListDirTool(Tool):
    """List contents of a directory."""

    def name(self) -> str:
        return "list_dir"

    def description(self) -> str:
        return "List the contents of a directory."

    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="Path to the directory", required=True),
            ToolParameter(
                name="recursive", type="boolean", description="List recursively", required=False, default=False
            ),
        ]

    def execute(self, path: str, recursive: bool = False) -> ToolResult:
        try:
            # Expand home directory
            path = os.path.expanduser(path)

            if not os.path.exists(path):
                return ToolResult(success=False, data=None, error=f"Directory not found: {path}")

            if not os.path.isdir(path):
                return ToolResult(success=False, data=None, error=f"Not a directory: {path}")

            lines = [f"Contents of {path}:", ""]

            if recursive:
                for root, dirs, files in os.walk(path):
                    level = root.replace(path, "").count(os.sep)
                    indent = "  " * level
                    lines.append(f"{indent}{os.path.basename(root)}/")
                    sub_indent = "  " * (level + 1)
                    for file in files:
                        lines.append(f"{sub_indent}{file}")
            else:
                for item in sorted(os.listdir(path)):
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        lines.append(f"📁 {item}/")
                    else:
                        lines.append(f"📄 {item}")

            return ToolResult(success=True, data="\n".join(lines))

        except Exception as e:
            return ToolResult(success=False, data=None, error=f"List failed: {str(e)}")


class ExecuteCommandTool(Tool):
    """Execute a shell command."""

    def name(self) -> str:
        return "execute_command"

    def description(self) -> str:
        return "Execute a shell command safely. Limited to safe commands only."

    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="command", type="string", description="Command to execute", required=True),
            ToolParameter(name="timeout", type="integer", description="Timeout in seconds", required=False, default=30),
        ]

    # List of forbidden commands/patterns
    FORBIDDEN_PATTERNS = [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf *",
        "> /dev/",
        "mkfs",
        "dd if=",
        ":(){ :|:& };:",  # Fork bomb
    ]

    def execute(self, command: str, timeout: int = 30) -> ToolResult:
        try:
            # Security check
            command_lower = command.lower()
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern in command_lower:
                    return ToolResult(success=False, data=None, error=f"Command blocked for security: {pattern}")

            # Execute command
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            return ToolResult(
                success=result.returncode == 0,
                data=output,
                error=f"Exit code: {result.returncode}" if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error=f"Command timed out after {timeout} seconds")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Execution failed: {str(e)}")


class GetTimeTool(Tool):
    """Get current time and date."""

    def name(self) -> str:
        return "get_time"

    def description(self) -> str:
        return "Get the current time and date."

    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="format",
                type="string",
                description="Time format (e.g., '%Y-%m-%d %H:%M:%S')",
                required=False,
                default="%Y-%m-%d %H:%M:%S",
            )
        ]

    def execute(self, format: str = "%Y-%m-%d %H:%M:%S") -> ToolResult:
        try:
            current_time = time.strftime(format)
            return ToolResult(success=True, data=f"Current time: {current_time}")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Failed to get time: {str(e)}")


# Function to register all built-in tools
def register_builtin_tools(registry):
    """Register all built-in tools."""
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListDirTool())
    registry.register(ExecuteCommandTool())
    registry.register(GetTimeTool())
