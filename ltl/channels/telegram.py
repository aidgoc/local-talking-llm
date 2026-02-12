"""Telegram bot integration for LTL.

Uses python-telegram-bot library (open source, free).
"""

import os
import sys
import threading
import time
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.channels import Channel
from ltl.core.bus import MessageBus, InboundMessage, OutboundMessage


class TelegramChannel(Channel):
    """Telegram bot channel for LTL."""

    def __init__(self, bus: MessageBus, token: str, allowed_users: List[str] = None):
        super().__init__("telegram", bus)
        self.token = token
        self.allowed_users = allowed_users or []
        self.bot = None
        self.updater = None

    def start(self):
        """Start the Telegram bot."""
        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
        except ImportError:
            print("❌ python-telegram-bot not installed. Install with: pip install python-telegram-bot")
            return

        if not self.token:
            print("❌ Telegram bot token not configured")
            return

        # Create application
        self.application = Application.builder().token(self.token).build()

        # Add handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Start polling in a separate thread
        self.running = True
        self.thread = threading.Thread(target=self._run_polling, daemon=True)
        self.thread.start()

        print(f"✅ Telegram bot started (token: {self.token[:10]}...)")

    def stop(self):
        """Stop the Telegram bot."""
        self.running = False
        if self.application:
            try:
                # Stop the application
                self.application.stop()
                print("✅ Telegram bot stopped")
            except Exception as e:
                print(f"⚠️ Error stopping Telegram bot: {e}")

    def _run_polling(self):
        """Run the polling loop."""
        try:
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            print(f"❌ Telegram polling error: {e}")
            self.running = False

    def send_message(self, chat_id: str, content: str, **kwargs):
        """Send a message to a Telegram chat."""
        if not self.application:
            return

        try:
            # Send message asynchronously
            async def send():
                await self.application.bot.send_message(chat_id=chat_id, text=content)

            # Run in event loop
            import asyncio

            asyncio.run(send())

        except Exception as e:
            print(f"❌ Failed to send Telegram message: {e}")

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        chat_id = str(update.effective_chat.id)

        if self._is_user_allowed(str(user.id)):
            welcome_msg = (
                f"Hello {user.first_name}! I'm LTL, your local talking assistant. Send me a message to get started!"
            )
            await update.message.reply_text(welcome_msg)
        else:
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages."""
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        message_text = update.message.text

        # Check if user is allowed
        if not self._is_user_allowed(str(user.id)):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        # Create inbound message
        inbound_msg = InboundMessage(
            channel="telegram",
            sender_id=str(user.id),
            chat_id=chat_id,
            content=message_text,
            session_key=f"telegram:{chat_id}",
            metadata={
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )

        # Publish to bus
        self.bus.publish_inbound(inbound_msg)

        # Send typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    def _is_user_allowed(self, user_id: str) -> bool:
        """Check if user is allowed to use the bot."""
        if not self.allowed_users:
            return True  # Allow all if no restrictions
        return user_id in self.allowed_users


def create_telegram_channel(bus: MessageBus, config: dict) -> Optional[TelegramChannel]:
    """Create a Telegram channel from config."""
    if not config.get("enabled", False):
        return None

    token = config.get("token", "")
    allowed_users = config.get("allow_from", [])

    if not token:
        print("⚠️ Telegram bot token not configured")
        return None

    return TelegramChannel(bus, token, allowed_users)
