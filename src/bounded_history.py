"""Bounded chat history to prevent unbounded memory growth."""

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import BaseMessage

from src.logging_config import get_logger

log = get_logger(__name__)


class BoundedChatHistory(InMemoryChatMessageHistory):
    """Chat history that prunes oldest message pairs when max_messages is exceeded."""

    max_messages: int = 50

    def add_message(self, message: BaseMessage) -> None:
        super().add_message(message)
        self._prune()

    def _prune(self) -> None:
        """Remove oldest message pairs (user+assistant) to stay under the limit."""
        if len(self.messages) <= self.max_messages:
            return

        overflow = len(self.messages) - self.max_messages
        # Remove in pairs to keep conversation coherent
        remove_count = overflow if overflow % 2 == 0 else overflow + 1
        remove_count = min(remove_count, len(self.messages))

        log.debug("Pruning %d messages from chat history (had %d, max %d)",
                  remove_count, len(self.messages), self.max_messages)

        self.messages = self.messages[remove_count:]
