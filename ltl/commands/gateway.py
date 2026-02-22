"""Gateway command - Start the message gateway for channels.

Routes messages between channels and the assistant.
Uses the full agent framework: Orchestrator intent routing → WebSearch / ToolExecutor / RLMClient.
"""

import logging
import os
import sys
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


def _init_agent_components(cfg: dict) -> dict:
    """Initialise Orchestrator, ToolExecutor, and WebSearch. Returns a components dict."""
    components = {"orchestrator": None, "tool_executor": None, "web_search": None}

    try:
        from src.orchestrator import Orchestrator
        components["orchestrator"] = Orchestrator(cfg)
    except Exception as e:
        log.warning("Orchestrator unavailable: %s", e)

    try:
        from src.web_search import WebSearch
        components["web_search"] = WebSearch(cfg.get("tools", {}).get("web", {}).get("search", {}))
    except Exception as e:
        log.warning("WebSearch unavailable: %s", e)

    try:
        from src.database import DatabaseManager
        from src.tools import ToolExecutor
        db = DatabaseManager("~/.local/share/talking-llm/assistant.db")
        db.init_db()
        components["tool_executor"] = ToolExecutor(db, cfg)
    except Exception as e:
        log.warning("ToolExecutor unavailable: %s", e)

    return components


def _route_message(text: str, rlm_holder: dict, components: dict) -> str:
    """Route a message through the agent framework and return a response string."""
    orchestrator = components.get("orchestrator")
    tool_executor = components.get("tool_executor")
    web_search = components.get("web_search")
    rlm_client = rlm_holder.get("client")

    intent = {"intent": "chat"}
    if orchestrator:
        try:
            intent = orchestrator.classify_intent(text)
        except Exception as e:
            log.warning("Orchestrator failed: %s", e)

    intent_type = intent.get("intent", "chat")

    if intent_type == "search" and web_search:
        try:
            query = intent.get("search_query") or text
            results = web_search.search_and_format(query, max_results=3)
            if rlm_client and results != "No search results found.":
                # Trim each snippet to 200 chars to keep the prompt short
                trimmed = "\n\n".join(
                    line if not line.startswith("    Snippet:") else
                    "    Snippet: " + line[12:212]
                    for line in results.splitlines()
                )
                prompt = (
                    f"Q: {text}\n\nSearch results:\n{trimmed}\n\n"
                    "Answer in 1-3 sentences:"
                )
                return rlm_client.get_response(prompt)
            return results
        except Exception as e:
            log.error("Search routing failed: %s", e)

    elif intent_type == "tool" and tool_executor:
        try:
            return tool_executor.extract_and_execute(text)
        except Exception as e:
            log.error("Tool routing failed: %s", e)

    # Default: plain chat via RLM
    if rlm_client:
        try:
            return rlm_client.get_response(text)
        except Exception as e:
            log.error("RLM error: %s", e)
            return "Sorry, I couldn't process that request. Please try again."

    return "Assistant is currently unavailable. Please try again later."


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

    rlm_holder: dict = {"client": None}
    try:
        rlm_holder["client"] = RLMClient(cfg)
    except Exception:
        pass

    components = _init_agent_components(cfg)

    # Give the telegram channel access to rlm_holder so /model can hot-swap the client
    for ch in manager.channels.values():
        ch._config = cfg
        ch._rlm_holder = rlm_holder

    threading.Thread(target=process_messages, args=(rlm_holder, components), daemon=True).start()
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

    telegram_config = channels_config.get("telegram", {})
    if telegram_config.get("enabled", False):
        telegram_channel = create_telegram_channel(bus, telegram_config)
        if telegram_channel:
            manager.register_channel(telegram_channel)

    discord_config = channels_config.get("discord", {})
    if discord_config.get("enabled", False):
        discord_channel = create_discord_channel(bus, discord_config)
        if discord_channel:
            manager.register_channel(discord_channel)

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
    }
  }
}
        """)
        return

    print(f"✓ Channels enabled: {', '.join(enabled_channels)}")
    print("✓ Message bus started")

    manager.start_all()

    rlm_holder: dict = {"client": None}
    try:
        rlm_holder["client"] = RLMClient(cfg)
        print("✓ RLMClient ready")
    except Exception as e:
        print(f"⚠️  RLMClient unavailable ({e}) — falling back to echo")

    components = _init_agent_components(cfg)
    enabled_components = [k for k, v in components.items() if v is not None]
    print(f"✓ Agent components: {', '.join(enabled_components) or 'none'}")

    # Give channels access to rlm_holder so /model can hot-swap the client
    for ch in manager.channels.values():
        ch._config = cfg
        ch._rlm_holder = rlm_holder

    processing_thread = threading.Thread(
        target=process_messages, args=(rlm_holder, components), daemon=True
    )
    processing_thread.start()

    print("\n✅ Gateway started! Press Ctrl+C to stop")
    print("=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down gateway...")

    manager.stop_all()
    bus.stop()
    print("✅ Gateway stopped")


def process_messages(rlm_holder: dict, components: dict):
    """Process inbound messages using the full agent framework.

    Args:
        rlm_holder:  {"client": RLMClient | None} — mutable for /model hot-swap.
        components:  {"orchestrator", "tool_executor", "web_search"} from _init_agent_components.
    """
    bus = get_bus()

    while True:
        try:
            msg = bus.consume_inbound(timeout=1.0)
            if not msg:
                continue

            print(f"📨 [{msg.channel}] {msg.sender_id}: {msg.content[:50]}...")

            response = _route_message(msg.content, rlm_holder, components)

            bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response,
                timestamp=time.time(),
            ))

        except Exception as e:
            print(f"❌ Message processing error: {e}")
            time.sleep(1)
