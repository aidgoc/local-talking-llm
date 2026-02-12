"""Orchestrator - fast keyword-based intent classifier.

Strategy: comprehensive keyword matching (0ms) + default to chat.
No LLM call needed -- fast-path covers 95%+ of voice commands,
and 'chat' is the safe default for anything ambiguous.
"""

from rich.console import Console


def _make_result(
    intent: str,
    confidence: float = 0.9,
    search_query: str = "",
    vision_prompt: str = "",
    reasoning: str = "",
) -> dict:
    return {
        "intent": intent,
        "confidence": confidence,
        "search_query": search_query,
        "vision_prompt": vision_prompt,
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# Keyword sets -- ordered by priority (vision > search > tool > system)
# ---------------------------------------------------------------------------

_VISION_PHRASES = [
    "take a photo", "take photo", "take a picture", "take picture",
    "click a photo", "click photo", "click a picture", "click picture",
    "click an image", "click image", "snap a photo", "snap photo",
    "capture image", "capture photo", "capture a photo",
    "what do you see", "what can you see", "describe what you see",
    "look at this", "look at that", "show me what",
    "open camera", "use camera", "use the camera",
    "scan this", "scan that", "read this label", "read this text",
    "what does this look like", "what does that look like",
    "what is this", "what is that",  # physical object context
    "what am i holding", "what's in front of me",
    "describe this", "describe that", "analyze this image",
    "identify this", "identify that",
]
_VISION_WORDS = {"camera", "photograph", "snapshot", "selfie", "webcam"}

_SEARCH_PHRASES = [
    "search for", "search about", "look up", "find out about",
    "google", "what is the latest", "latest news", "recent news",
    "current price", "price of", "stock price",
    "weather in", "weather today", "weather tomorrow", "weather forecast",
    "is it going to rain", "will it rain", "is it raining",
    "how much does", "how much is", "how much are",
    "news about", "news on", "headlines",
    "who won", "score of", "results of", "match result",
    "what happened in", "what's happening",
    "release date", "when does", "when will",
    "reviews of", "review for", "rating of",
    "directions to", "how to get to", "route to",
    "translate", "definition of", "define ",
    "recipe for", "how to make", "how to cook",
    "convert ", "exchange rate",
]

_TOOL_PHRASES = [
    # Memory: save
    "remember that", "remember my", "remember this", "remember me",
    "save this", "save that", "note this", "note that", "note down",
    "don't forget", "do not forget", "keep in mind",
    "my name is", "my birthday is", "my favorite", "i like",
    "i prefer", "i live in", "i work at", "i am from",
    # Memory: recall
    "what did i tell you", "what do you know about",
    "what do you remember", "do you remember",
    "what's my", "what is my",
    # Memory: list/delete
    "list memories", "show memories", "show what you remember",
    "what do you know", "everything you know",
    "delete memory", "forget about", "forget that", "forget my",
    # Tasks: create
    "create a task", "create task", "add a task", "add task",
    "add a todo", "add todo", "add to do", "add to my list",
    "remind me to", "remind me about",
    "i need to", "i have to", "i should",
    "put on my list", "add to list",
    # Tasks: list
    "list my tasks", "show my tasks", "what are my tasks",
    "my todos", "my to-dos", "my to dos", "my task list",
    "pending tasks", "open tasks", "what do i need to do",
    # Tasks: complete/delete
    "complete task", "finish task", "mark as done", "mark done",
    "task is done", "task done", "done with", "finished with",
    "delete task", "remove task", "cancel task",
    # Time
    "what time is it", "current time", "what's the time",
    "today's date", "what day is it", "what is today",
    "what's today", "what date is it",
    # Location
    "where am i", "my location", "what's my location",
    "what city am i in", "which city",
]
_TOOL_WORDS = {"birthday", "schedule", "appointment", "deadline"}

_SYSTEM_PHRASES = [
    "stop listening", "shut down", "shut it down",
    "show status", "system status", "help me with settings",
    "turn off", "go to sleep", "good night", "goodbye", "good bye",
    "i want to stop", "stop the assistant", "close the app",
]
_SYSTEM_WORDS = {"exit", "quit", "shutdown"}


class Orchestrator:
    """Fast keyword-based intent classifier. No LLM call needed."""

    def __init__(self, config: dict, console: Console | None = None):
        self.console = console or Console()

    def classify_intent(self, user_text: str) -> dict:
        """Classify user intent via keyword matching. Defaults to chat."""
        result = self._classify(user_text)
        self.console.print(
            f"[dim]Intent: {result['intent']} ({result['reasoning']})[/dim]"
        )
        return result

    def _classify(self, text: str) -> dict:
        lower = text.lower().strip()
        words = set(lower.split())

        # 1. Vision (highest priority -- user explicitly wants camera)
        for kw in _VISION_PHRASES:
            if kw in lower:
                return _make_result(
                    "vision", 0.95, vision_prompt=text, reasoning=f"matched '{kw}'"
                )
        if words & _VISION_WORDS:
            matched = words & _VISION_WORDS
            return _make_result(
                "vision", 0.85, vision_prompt=text,
                reasoning=f"keyword '{next(iter(matched))}'",
            )

        # 2. Search (needs web data)
        for kw in _SEARCH_PHRASES:
            if kw in lower:
                return _make_result(
                    "search", 0.9, search_query=text, reasoning=f"matched '{kw}'"
                )

        # 3. Tool (memory, tasks, time, location)
        for kw in _TOOL_PHRASES:
            if kw in lower:
                return _make_result("tool", 0.9, reasoning=f"matched '{kw}'")
        if words & _TOOL_WORDS:
            matched = words & _TOOL_WORDS
            return _make_result(
                "tool", 0.8, reasoning=f"keyword '{next(iter(matched))}'"
            )

        # 4. System
        for kw in _SYSTEM_PHRASES:
            if kw in lower:
                return _make_result("system", 0.9, reasoning=f"matched '{kw}'")
        if words & _SYSTEM_WORDS:
            matched = words & _SYSTEM_WORDS
            return _make_result(
                "system", 0.9, reasoning=f"keyword '{next(iter(matched))}'"
            )

        # 5. Default: chat (safe fallback, no LLM call)
        return _make_result("chat", 0.7, reasoning="default")
