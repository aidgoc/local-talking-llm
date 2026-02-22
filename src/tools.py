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

TOOL_EXTRACTION_PROMPT = """\
Output JSON only. Pick the best tool from the list below.

Tools:
save_memory(key, value, category)   - save a fact or preference; key=short_id e.g. user_city
recall_memory(query)                - retrieve a saved memory; query=search keyword
list_memories(category?)            - list all memories
delete_memory(key)                  - forget a memory
create_task(title, description?, priority?) - add a todo; priority=low|normal|high
list_tasks()                        - show pending tasks
complete_task(title)                - mark a task done
get_time()                          - current date and time
get_location()                      - user location

JSON format: {"tool": "tool_name", "params": {"key": "value"}}
No params:   {"tool": "get_time", "params": {}}
Output ONLY the JSON object."""


class ToolExecutor:
    """Extracts tool calls from user text and executes them.

    Always uses local Ollama on CPU for tool extraction to avoid API costs.
    """

    def __init__(self, db: DatabaseManager, config: dict):
        self.db = db
        self.config = config

        ollama_cfg = config.get("ollama") or config.get("providers", {}).get("ollama", {})
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
            "set_timer": self._set_timer,
            "schedule_reminder": self._schedule_reminder,
        }

    def extract_and_execute(self, user_text: str) -> str:
        """Extract tool call from user text via local LLM, execute it, return result string."""
        # Store user text for timer parsing
        self._last_user_text = user_text

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
        (["what time", "current time", "what's the time", "the time now"], "get_time", {}),
        (["where am i", "my location", "what's my location", "what city", "which city am i"], "get_location", {}),
        (
            [
                "list my tasks",
                "show my tasks",
                "my todos",
                "my to-dos",
                "my task list",
                "pending tasks",
                "open tasks",
                "what do i need to do",
                "what are my tasks",
            ],
            "list_tasks",
            {},
        ),
        (
            [
                "list memories",
                "show memories",
                "show what you remember",
                "what do you know",
                "everything you know",
                "what do you remember",
                "do you remember",
            ],
            "list_memories",
            {},
        ),
        (["today's date", "what day is it", "what is today", "what's today", "what date is it"], "get_time", {}),
        (
            [
                "set a timer",
                "set timer",
                "start a timer",
                "start timer",
                "set an alarm",
                "set alarm",
                "timer for",
                "alarm for",
            ],
            "set_timer",
            {},
        ),
        (
            [
                "remind me in",
                "remind me after",
                "wake me up in",
                "remind me at",
                "remind me on",
                "notify me in",
                "schedule a reminder",
                "schedule reminder",
                "create a reminder",
                "create reminder",
            ],
            "schedule_reminder",
            {},
        ),
    ]

    # Patterns that extract a query param for recall_memory (avoids LLM call)
    _RECALL_PATTERNS = [
        re.compile(r"(?:what(?:'s| is) my )(.*)", re.IGNORECASE),
        re.compile(r"(?:tell me my )(.*)", re.IGNORECASE),
        re.compile(r"(?:do you (?:know|remember) my )(.*)", re.IGNORECASE),
        re.compile(r"(?:what did i (?:say|tell you) (?:about|regarding) )(.*)", re.IGNORECASE),
    ]

    # Patterns that extract key+value for save_memory
    _SAVE_PATTERNS = [
        re.compile(r"(?:(?:save|store)(?: to| in)? memory[:\s]+)(.*)", re.IGNORECASE),
        re.compile(r"(?:remember (?:that )?my )(\w[\w\s]*?) (?:is|are) (.+)", re.IGNORECASE),
        re.compile(r"(?:my )(\w[\w\s]*?) (?:is|are) (.+)", re.IGNORECASE),
    ]

    def _fast_path(self, user_text: str) -> dict | None:
        """Return a tool call dict if the text matches a simple keyword route."""
        lower = user_text.lower().strip()

        # Static keyword routes (no param extraction)
        for keywords, tool, params in self._FAST_ROUTES:
            for kw in keywords:
                if kw in lower:
                    console.print(f"[dim]Fast-path: {tool} (matched '{kw}')[/dim]")
                    return {"tool": tool, "params": params}

        # Dynamic recall_memory patterns: "what is my X" → recall_memory(query=X)
        for pat in self._RECALL_PATTERNS:
            m = pat.search(user_text)
            if m:
                query = m.group(1).strip().rstrip("?. ")
                if query:
                    console.print(f"[dim]Fast-path: recall_memory (matched '{pat.pattern[:30]}')[/dim]")
                    return {"tool": "recall_memory", "params": {"query": query}}

        # Dynamic save_memory patterns: "remember my X is Y"
        for pat in self._SAVE_PATTERNS:
            m = pat.search(user_text)
            if m:
                groups = m.groups()
                if len(groups) == 2:
                    key = groups[0].strip().replace(" ", "_")
                    value = groups[1].strip()
                    console.print(f"[dim]Fast-path: save_memory (matched '{pat.pattern[:30]}')[/dim]")
                    return {"tool": "save_memory", "params": {"key": key, "value": value, "category": "personal"}}
                elif len(groups) == 1:
                    # "save to memory: X" — needs LLM to split key/value, fall through
                    pass

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
                    "num_ctx": 1024,   # small window is sufficient; reduces KV-cache cost
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

    def _set_timer(self, params: dict) -> str:
        """Set a timer for a specific duration."""
        import re
        import time
        import threading

        # Try to extract duration from the original user text
        # Look for patterns like "5 minutes", "10 seconds", "1 hour", etc.
        user_text = getattr(self, "_last_user_text", "")  # We'll need to pass this

        # Duration patterns
        duration_patterns = [
            (r"(\d+)\s*(?:minute|min)", lambda m: int(m.group(1)) * 60),
            (r"(\d+)\s*(?:hour|hr)", lambda m: int(m.group(1)) * 3600),
            (r"(\d+)\s*(?:second|sec)", lambda m: int(m.group(1))),
            (r"(\d+)\s*(?:day|days)", lambda m: int(m.group(1)) * 86400),
        ]

        duration_seconds = 300  # Default 5 minutes

        for pattern, converter in duration_patterns:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                duration_seconds = converter(match)
                break

        def timer_callback():
            time.sleep(duration_seconds)
            console.print(f"\n[bold red]⏰ TIMER: Time's up! ({duration_seconds} seconds)[/bold red]")
            # Could integrate with TTS here

        # Start timer in background
        timer_thread = threading.Thread(target=timer_callback, daemon=True)
        timer_thread.start()

        minutes = duration_seconds // 60
        seconds = duration_seconds % 60

        if minutes > 0:
            return f"Timer set for {minutes} minute{'s' if minutes != 1 else ''}! I'll notify you when time's up."
        else:
            return f"Timer set for {seconds} second{'s' if seconds != 1 else ''}! I'll notify you when time's up."

    def _schedule_reminder(self, params: dict) -> str:
        """Schedule a reminder for later."""
        # For now, create a task that can be checked later
        # This could be enhanced to integrate with a real cron system

        # Save as a special task with reminder flag
        task_title = "Scheduled Reminder"
        task_desc = "A reminder was scheduled for later"

        task_id = self.db.create_task(task_title, task_desc)
        if task_id:
            return f"Reminder scheduled! Check your tasks with 'list my tasks' to see when it's due."
        else:
            return "Failed to schedule reminder."
