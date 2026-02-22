"""RLM (Recursive Language Models) wrapper for local-talking-llm.

Thin wrapper around RLM that auto-selects the openai (Ollama /v1) or
openrouter backend based on config["backend"], formats LangChain message
history into a plain-string prompt prefix, and exposes get_response().
"""

import os
from rlm import RLM
from langchain_core.messages import BaseMessage, HumanMessage
from src.logging_config import get_logger

log = get_logger(__name__)

_SYSTEM_PROMPT = "You are a helpful AI assistant. Be concise, accurate, and friendly."


class RLMClient:
    def __init__(self, config: dict):
        rlm_cfg = config.get("rlm", {})
        backend = config.get("backend", "ollama")
        max_depth = rlm_cfg.get("max_depth", 1)
        system_prompt = rlm_cfg.get("system_prompt", _SYSTEM_PROMPT)

        if backend in ("ollama", "auto"):
            # Support both top-level "ollama" key (default.yaml) and "providers.ollama" (config.json)
            ollama_cfg = config.get("ollama") or config.get("providers", {}).get("ollama", {})
            base_url = ollama_cfg.get("base_url", "http://localhost:11434").rstrip("/") + "/v1"
            self._rlm = RLM(
                backend="openai",
                backend_kwargs={
                    "api_key": "ollama",   # Ollama ignores the key
                    "base_url": base_url,
                    "model_name": ollama_cfg.get("text_model", "gemma3"),
                    "timeout": 120.0,      # local models can be slow
                },
                max_depth=max_depth,
                custom_system_prompt=system_prompt,
            )
        else:  # openrouter
            # Support both top-level "openrouter" key and "providers.openrouter"
            or_cfg = config.get("openrouter") or config.get("providers", {}).get("openrouter", {})
            self._rlm = RLM(
                backend="openrouter",
                backend_kwargs={
                    "api_key": os.environ.get("OPENROUTER_API_KEY", or_cfg.get("api_key", "")),
                    "model_name": or_cfg.get("text_model", "meta-llama/llama-3.3-70b-instruct:free"),
                },
                max_depth=max_depth,
                custom_system_prompt=system_prompt,
            )
        log.info("RLMClient ready (backend=%s, max_depth=%d)", backend, max_depth)

    def get_response(self, text: str, history: list[BaseMessage] | None = None) -> str:
        result = self._rlm.completion(self._build_prompt(text, history))
        # max_depth=0 returns a plain str; max_depth>0 returns an object with .response
        if isinstance(result, str):
            return result.strip()
        return result.response.strip()

    @staticmethod
    def _build_prompt(text: str, history: list[BaseMessage] | None) -> str:
        if not history:
            return text
        lines = []
        for m in history[-10:]:   # cap to avoid token blow-up
            role = "User" if isinstance(m, HumanMessage) else "Assistant"
            lines.append(f"{role}: {m.content}")
        return "[Previous conversation]\n" + "\n".join(lines) + "\n[End]\n\nUser: " + text
