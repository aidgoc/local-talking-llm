"""Persistent SQLite-backed chat history with token-aware summarization."""

import os
import sqlite3
from datetime import date
from typing import List

import requests
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from src.logging_config import get_logger

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_session_time ON chat_history(session_id, created_at);
"""


class PersistentHistory(InMemoryChatMessageHistory):
    """SQLite-backed chat history with token-aware summarization.

    Drop-in replacement for BoundedChatHistory / InMemoryChatMessageHistory.
    Persists every message to SQLite, restores context on restart, and
    summarizes old turns via Ollama when the token budget is approaching.
    """

    # Pydantic fields (InMemoryChatMessageHistory is a Pydantic BaseModel)
    db_path: str = "~/.local/share/talking-llm/chat_history.db"
    session_id: str = "default"
    token_budget: int = 3000           # ~75 % of qwen2.5:3b's 4096 context
    summarize_threshold: float = 0.8   # Summarize when 80 % full
    restore_messages: int = 100        # How many rows to reload on startup
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    def model_post_init(self, __context) -> None:  # noqa: N802
        """Called by Pydantic after __init__; sets up DB and loads history."""
        super().model_post_init(__context)
        self._db_path = os.path.expanduser(self.db_path)
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()
        self._load_from_db(self.restore_messages)

    # ------------------------------------------------------------------
    # Public API (LangChain-compatible)
    # ------------------------------------------------------------------

    def add_message(self, message: BaseMessage) -> None:
        """Persist to DB, add to memory, then maybe summarize."""
        token_count = self._estimate_tokens(message.content)
        self._db_insert(message.type, message.content, token_count)
        super().add_message(message)
        self._maybe_summarize()

    def clear(self) -> None:
        """Clear both in-memory and DB rows for this session."""
        super().clear()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM chat_history WHERE session_id = ?", (self.session_id,)
            )
        log.debug("Cleared history for session '%s'", self.session_id)

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Cheap token estimate: ~4 chars per token (no extra dependency)."""
        return max(1, len(text) // 4)

    def _total_tokens(self) -> int:
        return sum(self._estimate_tokens(m.content) for m in self.messages)

    # ------------------------------------------------------------------
    # Summarization
    # ------------------------------------------------------------------

    def _maybe_summarize(self) -> None:
        """If token usage exceeds threshold, summarize the oldest half."""
        if self._total_tokens() <= self.token_budget * self.summarize_threshold:
            return

        # Oldest 50 % of messages (keep at least the latest 2)
        n = max(2, len(self.messages) // 2)
        to_summarize = self.messages[:n]
        to_keep = self.messages[n:]

        log.info(
            "Token budget %.0f%% full — summarizing %d messages",
            self._total_tokens() / self.token_budget * 100,
            len(to_summarize),
        )

        summary_text = self._call_ollama_summary(to_summarize)
        if not summary_text:
            log.warning("Summarization failed — skipping to avoid data loss")
            return

        summary_msg = HumanMessage(
            content=f"[Summary of earlier conversation: {summary_text}]"
        )

        # Remove summarized rows from DB; insert summary row
        oldest_id, newest_id = self._db_id_range(len(to_summarize))
        if oldest_id is not None and newest_id is not None:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM chat_history "
                    "WHERE session_id = ? AND id BETWEEN ? AND ?",
                    (self.session_id, oldest_id, newest_id),
                )
            self._db_insert("summary", summary_msg.content, self._estimate_tokens(summary_msg.content))

        # Replace in-memory list
        self.messages = [summary_msg] + list(to_keep)
        log.debug("History compacted: 1 summary + %d messages", len(to_keep))

    def _call_ollama_summary(self, messages: List[BaseMessage]) -> str:
        """POST to Ollama /api/chat asking for a concise summary."""
        conversation = "\n".join(
            f"{m.type.upper()}: {m.content}" for m in messages
        )
        payload = {
            "model": self.ollama_model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a summarization assistant. "
                        "Summarize the following conversation in 3-5 sentences, "
                        "preserving all important facts, decisions, and context."
                    ),
                },
                {"role": "user", "content": conversation},
            ],
        }
        try:
            resp = requests.post(
                f"{self.ollama_base_url}/api/chat",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
        except Exception as exc:
            log.error("Ollama summarization error: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # SQLite helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _db_insert(self, role: str, content: str, token_count: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_history (session_id, role, content, token_count) "
                "VALUES (?, ?, ?, ?)",
                (self.session_id, role, content, token_count),
            )

    def _db_id_range(self, oldest_n: int):
        """Return (min_id, max_id) for the oldest N rows of this session."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM chat_history WHERE session_id = ? "
                "ORDER BY id ASC LIMIT ?",
                (self.session_id, oldest_n),
            ).fetchall()
        if not rows:
            return None, None
        ids = [r["id"] for r in rows]
        return ids[0], ids[-1]

    def _load_from_db(self, n: int = 100) -> None:
        """Restore the last N messages from the DB into memory (no re-persisting)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM ("
                "  SELECT id, role, content FROM chat_history "
                "  WHERE session_id = ? ORDER BY id DESC LIMIT ?"
                ") ORDER BY id ASC",
                (self.session_id, n),
            ).fetchall()

        for row in rows:
            role, content = row["role"], row["content"]
            if role in ("human", "user", "summary"):
                msg: BaseMessage = HumanMessage(content=content)
            else:
                msg = AIMessage(content=content)
            # Bypass add_message to avoid re-persisting or re-summarizing
            super().add_message(msg)

        if rows:
            log.info(
                "Restored %d messages for session '%s'", len(rows), self.session_id
            )


# ------------------------------------------------------------------
# Convenience factory
# ------------------------------------------------------------------

def make_session_id(prefix: str) -> str:
    """Return a daily session ID like 'voice-2025-07-14'."""
    return f"{prefix}-{date.today().isoformat()}"
