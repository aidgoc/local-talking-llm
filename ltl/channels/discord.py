"""Discord bot integration for LTL.

Uses discord.py library (open source, free).
"""

import os
import sys
import threading
import asyncio
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.channels import Channel
from ltl.core.bus import MessageBus, InboundMessage, OutboundMessage


class DiscordChannel(Channel):
    """Discord bot channel for LTL."""

    def __init__(self, bus: MessageBus, token: str, allowed_users: List[str] = None):
        super().__init__("discord", bus)
        self.token = token
        self.allowed_users = allowed_users or []
        self.client = None
        self.loop = None

    def start(self):
        """Start the Discord bot."""
        try:
            import discord
        except ImportError:
            print("❌ discord.py not installed. Install with: pip install discord.py")
            return

        if not self.token:
            print("❌ Discord bot token not configured")
            return

        # Create Discord client
        intents = discord.Intents.default()
        intents.message_content = True

        self.client = discord.Client(intents=intents)

        # Set up event handlers
        @self.client.event
        async def on_ready():
            print(f"✅ Discord bot logged in as {self.client.user}")

        @self.client.event
        async def on_message(message):
            await self._handle_message(message)

        # Start bot in a separate thread
        self.running = True
        self.thread = threading.Thread(target=self._run_bot, daemon=True)
        self.thread.start()

        print(f"✅ Discord bot starting (token: {self.token[:10]}...)")

    def stop(self):
        """Stop the Discord bot."""
        self.running = False
        if self.client and self.loop:
            try:
                # Stop the event loop
                self.loop.call_soon_threadsafe(self.loop.stop)
                print("✅ Discord bot stopped")
            except Exception as e:
                print(f"⚠️ Error stopping Discord bot: {e}")

    def _run_bot(self):
        """Run the Discord bot."""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.client.start(self.token))
        except Exception as e:
            print(f"❌ Discord bot error: {e}")
            self.running = False

    def send_message(self, chat_id: str, content: str, **kwargs):
        """Send a message to a Discord channel."""
        if not self.client or not self.loop:
            return

        try:

            async def send():
                channel = self.client.get_channel(int(chat_id))
                if channel:
                    await channel.send(content)

            # Send in event loop
            self.loop.call_soon_threadsafe(lambda: asyncio.create_task(send()))

        except Exception as e:
            print(f"❌ Failed to send Discord message: {e}")

    async def _handle_message(self, message):
        """Handle incoming Discord messages."""
        # Ignore messages from bots (including ourselves)
        if message.author.bot:
            return

        # Ignore messages that don't start with our mention or are in DMs
        if not isinstance(message.channel, discord.DMChannel):
            # Check if bot is mentioned
            if not any(mention.id == self.client.user.id for mention in message.mentions):
                return

        # Check if user is allowed
        user_id = str(message.author.id)
        if not self._is_user_allowed(user_id):
            await message.reply("Sorry, you're not authorized to use this bot.")
            return

        # Remove bot mention from message
        content = message.content
        if not isinstance(message.channel, discord.DMChannel):
            content = content.replace(f"<@{self.client.user.id}>", "").strip()

        # Create inbound message
        inbound_msg = InboundMessage(
            channel="discord",
            sender_id=user_id,
            chat_id=str(message.channel.id),
            content=content,
            session_key=f"discord:{message.channel.id}",
            metadata={
                "username": message.author.name,
                "discriminator": message.author.discriminator,
                "guild": message.guild.name if message.guild else "DM",
                "channel_name": message.channel.name if hasattr(message.channel, "name") else "DM",
            },
        )

        # Publish to bus
        self.bus.publish_inbound(inbound_msg)

        # Send typing indicator
        await message.channel.typing()

    def _is_user_allowed(self, user_id: str) -> bool:
        """Check if user is allowed to use the bot."""
        if not self.allowed_users:
            return True  # Allow all if no restrictions
        return user_id in self.allowed_users


def create_discord_channel(bus: MessageBus, config: dict) -> Optional[DiscordChannel]:
    """Create a Discord channel from config."""
    if not config.get("enabled", False):
        return None

    token = config.get("token", "")
    allowed_users = config.get("allow_from", [])

    if not token:
        print("⚠️ Discord bot token not configured")
        return None

    return DiscordChannel(bus, token, allowed_users)
