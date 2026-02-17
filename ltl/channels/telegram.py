"""Telegram bot integration for LTL.

Uses python-telegram-bot library (open source, free).
"""

import asyncio
import logging
import os
import sys
import threading
import time
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.channels import Channel
from ltl.core.bus import MessageBus, InboundMessage, OutboundMessage

log = logging.getLogger(__name__)

# Per-user rate limit: max messages per window
_RATE_LIMIT_MESSAGES = 20
_RATE_LIMIT_WINDOW = 60  # seconds
_MAX_MESSAGE_LENGTH = 4000  # Telegram limit is 4096; leave headroom


class TelegramChannel(Channel):
    """Telegram bot channel for LTL."""

    def __init__(self, bus: MessageBus, token: str, allowed_users: List[str] = None):
        super().__init__("telegram", bus)
        self.token = token
        self.allowed_users = allowed_users or []
        self.application = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Per-user rate limiting: {user_id: [timestamps]}
        self._rate_timestamps: dict[str, list[float]] = {}
        self._rate_lock = threading.Lock()

        if not self.allowed_users:
            log.warning(
                "Telegram allow_from is empty — ALL Telegram users can message this bot. "
                "Set allow_from in ~/.ltl/config.json to restrict access."
            )

    def start(self):
        """Start the Telegram bot."""
        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
        except ImportError:
            log.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return

        self.Update = Update

        if not self.token:
            log.error("Telegram bot token not configured")
            return

        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Register outbound handler so the bus delivers replies back to Telegram
        self.bus.register_channel_handler("telegram", self._deliver_outbound)

        # Start polling in its own event loop (avoids set_wakeup_fd main-thread restriction)
        self.running = True
        self.thread = threading.Thread(target=self._run_polling, daemon=True)
        self.thread.start()

        log.info("Telegram bot started")
        print("✅ Telegram bot started")

    def stop(self):
        """Stop the Telegram bot."""
        self.running = False
        log.info("Telegram bot stopped")
        print("✅ Telegram bot stopped")

    def _run_polling(self):
        """Run the polling loop in its own asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_polling())
        except Exception as e:
            log.error("Telegram polling error: %s", e)
            self.running = False
        finally:
            self._loop.close()
            self._loop = None

    async def _async_polling(self):
        """Manage the full Telegram application lifecycle without signal handlers."""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=self.Update.ALL_TYPES)
        log.info("Telegram polling active")
        print("✅ Telegram polling active")
        while self.running:
            await asyncio.sleep(1)
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    def _deliver_outbound(self, msg):
        """Called by the bus to deliver an outbound message back to Telegram."""
        self.send_message(msg.chat_id, msg.content)

    def send_message(self, chat_id: str, content: str, **kwargs):
        """Send a message to a Telegram chat."""
        if not self.application or not self._loop:
            return

        async def _send():
            await self.application.bot.send_message(chat_id=chat_id, text=content)

        try:
            # Schedule into the existing polling event loop (thread-safe)
            future = asyncio.run_coroutine_threadsafe(_send(), self._loop)
            future.result(timeout=15)
        except Exception as e:
            log.error("Failed to send Telegram message to %s: %s", chat_id, e)

    def _is_rate_limited(self, user_id: str) -> bool:
        """Return True if this user has exceeded the rate limit."""
        now = time.time()
        with self._rate_lock:
            timestamps = self._rate_timestamps.get(user_id, [])
            # Drop timestamps outside the window
            timestamps = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
            if len(timestamps) >= _RATE_LIMIT_MESSAGES:
                self._rate_timestamps[user_id] = timestamps
                return True
            timestamps.append(now)
            self._rate_timestamps[user_id] = timestamps
            return False

    def _is_user_allowed(self, user_id: str) -> bool:
        """Check if user is allowed to use the bot."""
        if not self.allowed_users:
            return True  # Empty = allow all (warn logged at startup)
        return user_id in self.allowed_users

    async def _handle_start(self, update, context):
        """Handle /start command."""
        user = update.effective_user
        if self._is_user_allowed(str(user.id)):
            await update.message.reply_text(
                f"Hello {user.first_name}! I'm LTL, your local talking assistant. "
                "Send me a message to get started!"
            )
        else:
            log.warning("Unauthorized /start from user %s", user.id)
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")

    async def _handle_message(self, update, context):
        """Handle incoming messages."""
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        message_text = update.message.text or ""

        # Authorization check
        if not self._is_user_allowed(str(user.id)):
            log.warning("Unauthorized message from user %s", user.id)
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        # Rate limiting
        if self._is_rate_limited(str(user.id)):
            log.warning("Rate limit hit for user %s", user.id)
            await update.message.reply_text(
                f"You're sending messages too fast. Limit: {_RATE_LIMIT_MESSAGES} per minute."
            )
            return

        # Input length check
        if len(message_text) > _MAX_MESSAGE_LENGTH:
            await update.message.reply_text(
                f"Message too long (max {_MAX_MESSAGE_LENGTH} characters)."
            )
            return

        log.info("Message from user %s (len=%d)", user.id, len(message_text))

        inbound_msg = InboundMessage(
            channel="telegram",
            sender_id=str(user.id),
            chat_id=chat_id,
            content=message_text,
            session_key=f"telegram:{chat_id}",
            timestamp=time.time(),
            metadata={"username": user.username},  # only non-sensitive field
        )

        self.bus.publish_inbound(inbound_msg)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")


def create_telegram_channel(bus: MessageBus, config: dict) -> Optional[TelegramChannel]:
    """Create a Telegram channel from config."""
    if not config.get("enabled", False):
        return None

    # Prefer env var over config file for the token
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("token", "")
    allowed_users = config.get("allow_from", [])

    if not token:
        log.warning("Telegram bot token not configured")
        return None

    return TelegramChannel(bus, token, allowed_users)
