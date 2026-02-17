"""Gateway command - Start the message gateway for channels.

Routes messages between channels and the assistant.
"""

import logging
import os
import sys
import signal
import time
import threading

log = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.core.bus import get_bus, OutboundMessage
from ltl.core.config import load_config
from ltl.channels import get_manager
from ltl.channels.telegram import create_telegram_channel
from ltl.channels.discord import create_discord_channel
from src.rlm_client import RLMClient


def start_background(cfg: dict) -> list[str]:
    """Start the gateway in background threads (non-blocking).

    Returns the list of enabled channel names, or [] if none configured.
    Called automatically by the TUI on startup.
    """
    bus = get_bus()
    bus.start()

    manager = get_manager(bus)
    channels_config = cfg.get("channels", {})

    telegram_config = channels_config.get("telegram", {})
    if telegram_config.get("enabled", False):
        ch = create_telegram_channel(bus, telegram_config)
        if ch:
            manager.register_channel(ch)

    discord_config = channels_config.get("discord", {})
    if discord_config.get("enabled", False):
        ch = create_discord_channel(bus, discord_config)
        if ch:
            manager.register_channel(ch)

    registered = list(manager.channels.keys())
    if not registered:
        return []

    manager.start_all()

    rlm_client = None
    try:
        rlm_client = RLMClient(cfg)
    except Exception:
        pass

    threading.Thread(target=process_messages, args=(rlm_client,), daemon=True).start()
    return registered


def run(args):
    """Run the gateway command."""
    print("🎙️  LTL Gateway\n")
    print("=" * 60)

    # Load configuration
    try:
        cfg = load_config()
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return

    # Initialize message bus
    bus = get_bus()
    bus.start()

    # Initialize channel manager
    manager = get_manager(bus)

    # Create and register channels
    channels_config = cfg.get("channels", {})

    # Telegram channel
    telegram_config = channels_config.get("telegram", {})
    if telegram_config.get("enabled", False):
        telegram_channel = create_telegram_channel(bus, telegram_config)
        if telegram_channel:
            manager.register_channel(telegram_channel)

    # Discord channel
    discord_config = channels_config.get("discord", {})
    if discord_config.get("enabled", False):
        discord_channel = create_discord_channel(bus, discord_config)
        if discord_channel:
            manager.register_channel(discord_channel)

    # Start all channels
    enabled_channels = list(manager.channels.keys())
    if not enabled_channels:
        print("⚠️ No channels enabled. Configure channels in ~/.ltl/config.json")
        print("\nExample configuration:")
        print("""
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allow_from": ["YOUR_USER_ID"]
    },
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allow_from": ["YOUR_USER_ID"]
    }
  }
}
        """)
        return

    print(f"✓ Channels enabled: {', '.join(enabled_channels)}")
    print("✓ Message bus started")

    # Start channels
    manager.start_all()

    # Init RLM client for responding to messages
    rlm_client = None
    try:
        rlm_client = RLMClient(cfg)
        print("✓ RLMClient ready")
    except Exception as e:
        print(f"⚠️  RLMClient unavailable ({e}) — falling back to echo")

    # Start message processing thread
    processing_thread = threading.Thread(target=process_messages, args=(rlm_client,), daemon=True)
    processing_thread.start()

    print("\n✅ Gateway started! Press Ctrl+C to stop")
    print("=" * 60)

    # Wait for shutdown signal
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down gateway...")

    # Stop everything
    manager.stop_all()
    bus.stop()
    print("✅ Gateway stopped")


def process_messages(rlm_client):
    """Process inbound messages and route to assistant."""
    bus = get_bus()

    while True:
        try:
            # Get inbound message
            msg = bus.consume_inbound(timeout=1.0)
            if not msg:
                continue

            print(f"📨 [{msg.channel}] {msg.sender_id}: {msg.content[:50]}...")

            # Route to RLM assistant, fall back to generic message on error
            if rlm_client:
                try:
                    response = rlm_client.get_response(msg.content)
                except Exception as e:
                    log.error("RLM error for message from %s: %s", msg.sender_id, e)
                    response = "Sorry, I couldn't process that request. Please try again."
            else:
                response = "Assistant is currently unavailable. Please try again later."

            # Send response back to channel
            outbound_msg = OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=response, timestamp=time.time()
            )
            bus.publish_outbound(outbound_msg)

        except Exception as e:
            print(f"❌ Message processing error: {e}")
            time.sleep(1)
