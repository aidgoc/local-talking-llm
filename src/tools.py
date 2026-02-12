"""Tool system for the assistant - prompt-based tool calling with local LLM."""

import json
import re
from datetime import datetime

import requests
from rich.console import Console

from src.database import DatabaseManager
from src.logging_config import get_logger
from src.retry import retry_on_exception

console = Console()
log = get_logger(__name__)

# Tool descriptions for the LLM prompt
TOOL_DEFINITIONS = {
    "save_memory": {
        "description": "Save a fact, preference, or piece of information to remember later",
        "parameters": {
            "key": "short identifier like 'user_birthday', 'favorite_color', 'boss_name'",
            "value": "the information to remember",
            "category": "one of: personal, preference, fact, general (default: general)",
        },
    },
    "recall_memory": {
        "description": "Retrieve a previously saved memory by searching for it",
        "parameters": {
            "query": "search term to find the memory (e.g., 'birthday', 'color')",
        },
    },
    "list_memories": {
        "description": "List all saved memories, optionally filtered by category",
        "parameters": {
            "category": "optional filter: personal, preference, fact, general",
        },
    },
    "delete_memory": {
        "description": "Delete/forget a previously saved memory",
        "parameters": {
            "key": "the key of the memory to delete",
        },
    },
    "create_task": {
        "description": "Create a new task or todo item for the user",
        "parameters": {
            "title": "what needs to be done",
            "description": "optional extra details",
            "priority": "one of: low, normal, high (default: normal)",
        },
    },
    "list_tasks": {
        "description": "List the user's pending tasks",
        "parameters": {},
    },
    "complete_task": {
        "description": "Mark a task as completed/done",
        "parameters": {
            "title": "the task title or keywords to find it",
        },
    },
    "get_time": {
        "description": "Get the current date and time",
        "parameters": {},
    },
    "get_location": {
        "description": "Get the user's current location (city, region, country)",
        "parameters": {},
    },
}

# Build the tool description string for the LLM prompt once
_TOOL_DESC_LINES = []
for name, info in TOOL_DEFINITIONS.items():
    params = info["parameters"]
    param_str = ", ".join(f"{k}: {v}" for k, v in params.items()) if params else "none"
    _TOOL_DESC_LINES.append(f"- {name}: {info['description']}. Parameters: {param_str}")
TOOL_DESCRIPTIONS_TEXT = "\n".join(_TOOL_DESC_LINES)

TOOL_EXTRACTION_PROMPT = f"""\
You are a tool-calling assistant. Based on the user's message, select the best tool and extract its parameters.

Available tools:
{TOOL_DESCRIPTIONS_TEXT}

Respond with ONLY a JSON object:
{{"tool": "<tool_name>", "params": {{"param1": "value1", ...}}}}

If no parameters are needed, use an empty object: {{"tool": "list_tasks", "params": {{}}}}

Rules:
- Pick exactly ONE tool
- Extract parameter values from the user's message
- For save_memory, create a concise key from the subject (e.g., "user_birthday", "meeting_friday")
- For recall_memory, use the most relevant search keyword
- Output ONLY the JSON object, nothing else"""


class ToolExecutor:
    """Extracts tool calls from user text and executes them.

    Always uses local Ollama on CPU for tool extraction to avoid API costs.
    """

    def __init__(self, db: DatabaseManager, config: dict):
        self.db = db
        self.config = config

        ollama_cfg = config.get("ollama", {})
        self.ollama_base_url = ollama_cfg.get("base_url", "http://localhost:11434")
        self.orchestrator_model = ollama_cfg.get("orchestrator_model", "gemma3")
        self.orchestrator_num_gpu = ollama_cfg.get("orchestrator_num_gpu", 0)

        self._handlers = {
            "save_memory": self._save_memory,
            "recall_memory": self._recall_memory,
            "list_memories": self._list_memories,
            "delete_memory": self._delete_memory,
            "create_task": self._create_task,
            "list_tasks": self._list_tasks,
            "complete_task": self._complete_task,
            "get_time": self._get_time,
            "get_location": self._get_location,
        }

    def extract_and_execute(self, user_text: str) -> str:
        """Extract tool call from user text via local LLM, execute it, return result string."""
        # Step 0: Fast-path for simple tools (skip LLM entirely)
        fast = self._fast_path(user_text)
        if fast:
            tool_call = fast
        else:
            # Step 1: Extract tool call via local Ollama (CPU, no API cost)
            try:
                tool_call = self._extract_tool_call(user_text)
            except Exception as e:
                log.warning("Tool extraction failed: %s", e)
                console.print(f"[yellow]Tool extraction failed: {e}[/yellow]")
                return f"Could not determine the right action for: {user_text}"

        tool_name = tool_call.get("tool", "")
        params = tool_call.get("params", {})
        console.print(f"[dim]Tool: {tool_name}({params})[/dim]")

        # Step 2: Execute
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"Unknown tool: {tool_name}"

        try:
            return handler(params)
        except Exception as e:
            log.error("Tool execution error for %s: %s", tool_name, e)
            console.print(f"[red]Tool execution error: {e}[/red]")
            return f"Error executing {tool_name}: {e}"

    # -- Fast-path keyword routes (skip LLM for obvious tools) --

    _FAST_ROUTES: list[tuple[list[str], str, dict]] = [
        # (keywords, tool_name, default_params)
        (["what time", "current time", "what's the time", "the time now"],
         "get_time", {}),
        (["where am i", "my location", "what's my location", "what city",
          "which city am i"],
         "get_location", {}),
        (["list my tasks", "show my tasks", "my todos", "my to-dos",
          "my task list", "pending tasks", "open tasks",
          "what do i need to do", "what are my tasks"],
         "list_tasks", {}),
        (["list memories", "show memories", "show what you remember",
          "what do you know", "everything you know",
          "what do you remember", "do you remember"],
         "list_memories", {}),
        (["today's date", "what day is it", "what is today",
          "what's today", "what date is it"],
         "get_time", {}),
    ]

    def _fast_path(self, user_text: str) -> dict | None:
        """Return a tool call dict if the text matches a simple keyword route."""
        lower = user_text.lower().strip()
        for keywords, tool, params in self._FAST_ROUTES:
            for kw in keywords:
                if kw in lower:
                    console.print(f"[dim]Fast-path: {tool} (matched '{kw}')[/dim]")
                    return {"tool": tool, "params": params}
        return None

    def _extract_tool_call(self, user_text: str) -> dict:
        """Use local Ollama LLM (CPU) to extract tool name + params."""
        raw = self._ollama_extract(user_text)
        return self._parse_tool_json(raw)

    @retry_on_exception(max_retries=2, retryable_exceptions=(requests.ConnectionError, requests.Timeout))
    def _ollama_extract(self, user_text: str) -> str:
        """Call Ollama on CPU for tool extraction."""
        response = requests.post(
            f"{self.ollama_base_url}/api/chat",
            json={
                "model": self.orchestrator_model,
                "messages": [
                    {"role": "system", "content": TOOL_EXTRACTION_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "num_gpu": self.orchestrator_num_gpu,
                    "temperature": 0.1,
                    "num_predict": 150,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def _parse_tool_json(self, raw: str) -> dict:
        """Parse LLM response into {tool, params} dict."""
        # Try direct parse
        try:
            data = json.loads(raw)
            if "tool" in data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting JSON from text
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if "tool" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass

        raise ValueError(f"Could not parse tool call from: {raw[:100]}")

    # -- Tool handlers --

    def _save_memory(self, params: dict) -> str:
        key = params.get("key", "").strip()
        value = params.get("value", "").strip()
        category = params.get("category", "general").strip()
        if not key or not value:
            return "Missing key or value for save_memory"
        self.db.save_memory(key, value, category)
        return f"Saved: {key} = {value} (category: {category})"

    def _recall_memory(self, params: dict) -> str:
        query = params.get("query", "").strip()
        if not query:
            return "No search query provided for recall_memory"
        results = self.db.semantic_search_memories(query)
        if not results:
            return f"No memories found matching '{query}'"
        lines = [f"- {m['key']}: {m['value']}" for m in results]
        return "Found memories:\n" + "\n".join(lines)

    def _list_memories(self, params: dict) -> str:
        category = params.get("category", "").strip() or None
        results = self.db.list_memories(category=category)
        if not results:
            return "No memories saved yet."
        lines = [f"- {m['key']}: {m['value']} [{m['category']}]" for m in results]
        return f"{len(results)} memories:\n" + "\n".join(lines)

    def _delete_memory(self, params: dict) -> str:
        key = params.get("key", "").strip()
        if not key:
            return "No key provided for delete_memory"
        if self.db.delete_memory(key):
            return f"Deleted memory: {key}"
        return f"Memory '{key}' not found"

    def _create_task(self, params: dict) -> str:
        title = params.get("title", "").strip()
        if not title:
            return "No title provided for create_task"
        desc = params.get("description", "").strip()
        priority = params.get("priority", "normal").strip()
        task_id = self.db.create_task(title, desc, priority)
        return f"Created task #{task_id}: {title} (priority: {priority})"

    def _list_tasks(self, params: dict) -> str:
        tasks = self.db.list_tasks(status="pending")
        if not tasks:
            return "No pending tasks."
        lines = []
        for t in tasks:
            due = f" (due: {t['due_date']})" if t.get("due_date") else ""
            lines.append(f"- [{t['priority']}] {t['title']}{due}")
        return f"{len(tasks)} pending tasks:\n" + "\n".join(lines)

    def _complete_task(self, params: dict) -> str:
        title = params.get("title", "").strip()
        if not title:
            return "No task title provided for complete_task"
        task = self.db.find_task_by_title(title)
        if not task:
            return f"No pending task found matching '{title}'"
        self.db.complete_task(task["id"])
        return f"Completed task: {task['title']}"

    def _get_time(self, params: dict) -> str:
        now = datetime.now()
        return f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"

    def _get_location(self, params: dict) -> str:
        # Check cached location first
        cached = self.db.get_memory("_cached_location")
        if cached:
            return f"Location: {cached['value']}"

        # Try IP geolocation
        try:
            resp = requests.get("https://ipinfo.io/json", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                loc = f"{data.get('city', '?')}, {data.get('region', '?')}, {data.get('country', '?')}"
                # Cache it
                self.db.save_memory("_cached_location", loc, "system")
                self.db.save_memory("_cached_timezone", data.get("timezone", ""), "system")
                return f"Location: {loc} (timezone: {data.get('timezone', '?')})"
        except Exception:
            pass

        return "Location unavailable (no internet connection)"
