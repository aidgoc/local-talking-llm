"""Channel interfaces and base classes for LTL.

Provides unified interface for different chat platforms.
"""

import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Optional, Callable

from ltl.core.bus import MessageBus, InboundMessage, OutboundMessage


class Channel(ABC):
    """Base class for all chat channels."""

    def __init__(self, name: str, bus: MessageBus):
        self.name = name
        self.bus = bus
        self.running = False
        self.thread = None

    @abstractmethod
    def start(self):
        """Start the channel."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the channel."""
        pass

    @abstractmethod
    def send_message(self, chat_id: str, content: str, **kwargs):
        """Send a message to a chat."""
        pass

    def is_running(self) -> bool:
        """Check if channel is running."""
        return self.running


class ChannelManager:
    """Manages multiple channels."""

    def __init__(self, bus: MessageBus):
        self.bus = bus
        self.channels = {}

    def register_channel(self, channel: Channel):
        """Register a channel."""
        self.channels[channel.name] = channel

    def get_channel(self, name: str) -> Optional[Channel]:
        """Get a channel by name."""
        return self.channels.get(name)

    def start_all(self):
        """Start all registered channels."""
        for channel in self.channels.values():
            try:
                channel.start()
                print(f"✓ Started channel: {channel.name}")
            except Exception as e:
                print(f"✗ Failed to start channel {channel.name}: {e}")

    def stop_all(self):
        """Stop all registered channels."""
        for channel in self.channels.values():
            try:
                channel.stop()
                print(f"✓ Stopped channel: {channel.name}")
            except Exception as e:
                print(f"✗ Failed to stop channel {channel.name}: {e}")

    def get_enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return [name for name, channel in self.channels.items() if channel.is_running()]


# Global channel manager instance
_manager = None


def get_manager(bus: MessageBus = None) -> ChannelManager:
    """Get the global channel manager."""
    global _manager
    if _manager is None:
        if bus is None:
            from ltl.core.bus import get_bus

            bus = get_bus()
        _manager = ChannelManager(bus)
    return _manager
