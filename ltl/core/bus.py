"""Message bus system for LTL channels.

Inspired by PicoClaw's bus system - provides unified message routing
between channels and the assistant.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable
from queue import Queue, Full

log = logging.getLogger(__name__)

_INBOUND_MAXSIZE = 500
_OUTBOUND_MAXSIZE = 200


@dataclass
class InboundMessage:
    """Message from a channel to the assistant."""

    channel: str  # e.g., "telegram", "discord", "cli"
    sender_id: str  # User/channel identifier
    chat_id: str  # Chat/conversation identifier
    content: str  # Message content
    session_key: str  # Session identifier for conversation history
    timestamp: float  # Unix timestamp
    metadata: dict = None  # Additional channel-specific data

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class OutboundMessage:
    """Message from assistant to a channel."""

    channel: str  # Target channel
    chat_id: str  # Target chat/conversation
    content: str  # Message content
    timestamp: float  # Unix timestamp
    metadata: dict = None  # Additional channel-specific data

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp == 0:
            self.timestamp = time.time()


class MessageBus:
    """Unified message bus for channel communication.

    Handles routing messages between channels and the assistant.
    Similar to PicoClaw's bus system but simplified for LTL.
    """

    def __init__(self):
        self.inbound_queue = Queue(maxsize=_INBOUND_MAXSIZE)
        self.outbound_queues: dict[str, Queue] = {}
        self._handler_lock = threading.RLock()
        self._channel_handlers: dict[str, Callable] = {}
        self.running = False
        self.thread = None

    def start(self):
        """Start the message bus."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the message bus."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _run(self):
        """Main bus processing loop."""
        while self.running:
            try:
                # Process outbound messages
                for channel, queue in list(self.outbound_queues.items()):
                    try:
                        while not queue.empty():
                            msg = queue.get_nowait()
                            with self._handler_lock:
                                handler = self._channel_handlers.get(channel)
                            if handler:
                                try:
                                    handler(msg)
                                except Exception as he:
                                    log.error("Handler error for %s: %s", channel, he)
                            else:
                                log.debug("Outbound to %s:%s (no handler)", channel, msg.chat_id)
                    except Exception as e:
                        print(f"[BUS] Error processing outbound for {channel}: {e}")

                time.sleep(0.1)  # Small delay to prevent busy waiting

            except Exception as e:
                print(f"[BUS] Error in main loop: {e}")
                time.sleep(1)

    def publish_inbound(self, message: InboundMessage):
        """Publish an inbound message to the assistant."""
        try:
            self.inbound_queue.put_nowait(message)
        except Full:
            log.warning("Inbound queue full — dropping message from %s", message.sender_id)

    def consume_inbound(self, timeout: float = None) -> Optional[InboundMessage]:
        """Consume an inbound message (blocking)."""
        try:
            if timeout:
                return self.inbound_queue.get(timeout=timeout)
            else:
                return self.inbound_queue.get(block=False)
        except:
            return None

    def publish_outbound(self, message: OutboundMessage):
        """Publish an outbound message to a channel."""
        if message.channel not in self.outbound_queues:
            self.outbound_queues[message.channel] = Queue(maxsize=_OUTBOUND_MAXSIZE)
        try:
            self.outbound_queues[message.channel].put_nowait(message)
        except Full:
            log.warning("Outbound queue full for channel %s — dropping reply", message.channel)

    def register_channel_handler(self, channel: str, handler: Callable[[OutboundMessage], None]):
        """Register a handler for outbound messages to a specific channel."""
        with self._handler_lock:
            self._channel_handlers[channel] = handler

    def get_channel_queue(self, channel: str) -> Queue:
        """Get the outbound queue for a channel."""
        if channel not in self.outbound_queues:
            self.outbound_queues[channel] = Queue()
        return self.outbound_queues[channel]


# Global message bus instance
_bus = None


def get_bus() -> MessageBus:
    """Get the global message bus."""
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
