"""Telegram bot integration for LTL.

Uses python-telegram-bot library (open source, free).
Restores all Sentinel commands: /wake, /status, /search, /memory, /help.
"""

import asyncio
import base64
import logging
import os
import sys
import threading
import time
from io import BytesIO
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ltl.channels import Channel
from ltl.core.bus import MessageBus, InboundMessage, OutboundMessage

log = logging.getLogger(__name__)

_RATE_LIMIT_MESSAGES = 20
_RATE_LIMIT_WINDOW = 60       # seconds
_MAX_MESSAGE_LENGTH = 4000    # Telegram cap is 4096; leave headroom
_OLLAMA_URL = "http://localhost:11434"


class TelegramChannel(Channel):
    """Telegram bot channel for LTL."""

    def __init__(self, bus: MessageBus, token: str, allowed_users: List[str] = None):
        super().__init__("telegram", bus)
        self.token = token
        self.allowed_users = allowed_users or []
        self.application = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._rate_timestamps: dict[str, list[float]] = {}
        self._rate_lock = threading.Lock()

        if not self.allowed_users:
            log.warning(
                "Telegram allow_from is empty — ALL Telegram users can message this bot. "
                "Set allow_from in ~/.ltl/config.json to restrict access."
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

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

        # Core commands
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help",  self._handle_help))

        # Sentinel commands restored
        self.application.add_handler(CommandHandler("wake",   self._handle_wake))
        self.application.add_handler(CommandHandler("status", self._handle_status))
        self.application.add_handler(CommandHandler("search", self._handle_search))
        self.application.add_handler(CommandHandler("memory", self._handle_memory))

        # Regular text messages → LLM
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        self.bus.register_channel_handler("telegram", self._deliver_outbound)

        self.running = True
        self.thread = threading.Thread(target=self._run_polling, daemon=True)
        self.thread.start()

        log.info("Telegram bot started")
        print("✅ Telegram bot started")

    def stop(self):
        self.running = False
        log.info("Telegram bot stopped")
        print("✅ Telegram bot stopped")

    def _run_polling(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        retry = 0
        while self.running:
            try:
                self._loop.run_until_complete(self._async_polling())
                break  # clean exit
            except Exception as e:
                if "Conflict" in str(e):
                    wait = min(30, 5 * (retry + 1))
                    log.warning("Telegram conflict — another instance may be running. Retrying in %ds...", wait)
                    time.sleep(wait)
                    retry += 1
                else:
                    log.error("Telegram polling error: %s", e)
                    self.running = False
                    break
        self._loop.close()
        self._loop = None

    async def _async_polling(self):
        await self.application.initialize()
        # Flush any stale long-poll session before starting our own
        try:
            await self.application.bot.get_updates(offset=-1, timeout=0)
        except Exception:
            pass
        await self.application.start()
        await self.application.updater.start_polling(
            allowed_updates=self.Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        log.info("Telegram polling active")
        print("✅ Telegram polling active")
        while self.running:
            await asyncio.sleep(1)
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    # ------------------------------------------------------------------
    # Outbound delivery
    # ------------------------------------------------------------------

    def _deliver_outbound(self, msg):
        self.send_message(msg.chat_id, msg.content)

    def send_message(self, chat_id: str, content: str, **kwargs):
        if not self.application or not self._loop:
            return

        async def _send():
            await self.application.bot.send_message(chat_id=chat_id, text=content)

        try:
            future = asyncio.run_coroutine_threadsafe(_send(), self._loop)
            future.result(timeout=15)
        except Exception as e:
            log.error("Failed to send message to %s: %s", chat_id, e)

    def _send_photo(self, chat_id: str, photo_bytes: bytes, caption: str = ""):
        if not self.application or not self._loop:
            return

        async def _send():
            await self.application.bot.send_photo(
                chat_id=chat_id, photo=photo_bytes, caption=caption
            )

        try:
            future = asyncio.run_coroutine_threadsafe(_send(), self._loop)
            future.result(timeout=20)
        except Exception as e:
            log.error("Failed to send photo to %s: %s", chat_id, e)

    # ------------------------------------------------------------------
    # Security helpers
    # ------------------------------------------------------------------

    def _is_user_allowed(self, user_id: str) -> bool:
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users

    def _is_rate_limited(self, user_id: str) -> bool:
        now = time.time()
        with self._rate_lock:
            timestamps = [t for t in self._rate_timestamps.get(user_id, []) if now - t < _RATE_LIMIT_WINDOW]
            if len(timestamps) >= _RATE_LIMIT_MESSAGES:
                self._rate_timestamps[user_id] = timestamps
                return True
            timestamps.append(now)
            self._rate_timestamps[user_id] = timestamps
            return False

    def _auth_check(self, user_id: str) -> bool:
        """Log and return False if not authorised."""
        if not self._is_user_allowed(user_id):
            log.warning("Unauthorized access attempt from user %s", user_id)
            return False
        return True

    # ------------------------------------------------------------------
    # /start  /help
    # ------------------------------------------------------------------

    async def _handle_start(self, update, context):
        user = update.effective_user
        if not self._auth_check(str(user.id)):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return
        await update.message.reply_text(
            f"👋 Hello {user.first_name}! I'm LTL — your local AI assistant.\n\n"
            "Commands:\n"
            "  /wake     — 📸 Capture image + describe it\n"
            "  /status   — 🛡 System health\n"
            "  /search   — 🔍 Web search  (e.g. /search python tips)\n"
            "  /memory   — 🧠 Search history  (e.g. /memory meeting)\n"
            "  /help     — Show this message\n\n"
            "Or just send any message to chat with the AI."
        )

    async def _handle_help(self, update, context):
        await self._handle_start(update, context)

    # ------------------------------------------------------------------
    # /wake  — camera capture + Moondream description
    # ------------------------------------------------------------------

    async def _handle_wake(self, update, context):
        user = update.effective_user
        chat_id = str(update.effective_chat.id)

        if not self._auth_check(str(user.id)):
            await update.message.reply_text("Not authorized.")
            return

        await update.message.reply_text("📸 Capturing image…")
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

        loop = asyncio.get_event_loop()
        image_b64, image_bytes = await loop.run_in_executor(None, self._capture_image)

        if not image_b64:
            await update.message.reply_text("❌ Camera unavailable or capture failed.")
            return

        # Send the photo
        self._send_photo(chat_id, image_bytes, caption="📸 Captured")

        # Describe with vision model
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        description = await loop.run_in_executor(None, self._describe_image, image_b64)
        await update.message.reply_text(f"👁 {description}")

    def _capture_image(self) -> tuple[Optional[str], Optional[bytes]]:
        """Capture a frame from the camera. Returns (base64_str, jpeg_bytes)."""
        try:
            import cv2
            from PIL import Image

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None, None

            # Warm up: grab a few frames so auto-exposure settles
            for _ in range(5):
                cap.read()

            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None, None

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb).resize((512, 384))

            buf = BytesIO()
            pil_image.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()
            img_b64 = base64.b64encode(img_bytes).decode()

            log.info("Camera capture OK (%d KB)", len(img_bytes) // 1024)
            return img_b64, img_bytes

        except Exception as e:
            log.error("Camera capture failed: %s", e)
            return None, None

    def _describe_image(self, image_b64: str) -> str:
        """Describe image using Moondream via Ollama (GPU)."""
        try:
            import requests
            r = requests.post(
                f"{_OLLAMA_URL}/api/chat",
                json={
                    "model": "moondream",
                    "messages": [
                        {"role": "user", "content": "Describe what you see in this image.", "images": [image_b64]}
                    ],
                    "stream": False,
                    "options": {"num_gpu": 99},  # all layers on GPU
                },
                timeout=90,
            )
            if r.status_code == 200:
                return r.json()["message"]["content"].strip()
            log.warning("Vision model returned status %s", r.status_code)
            return "Could not describe the image."
        except Exception as e:
            log.error("Vision description failed: %s", e)
            return "Vision model unavailable."

    # ------------------------------------------------------------------
    # /status  — system health
    # ------------------------------------------------------------------

    async def _handle_status(self, update, context):
        if not self._auth_check(str(update.effective_user.id)):
            await update.message.reply_text("Not authorized.")
            return

        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(None, self._get_status)
        await update.message.reply_text(msg)

    def _get_status(self) -> str:
        import requests

        lines = ["🛡 LTL Status\n"]

        # Ollama
        try:
            r = requests.get(f"{_OLLAMA_URL}/api/tags", timeout=3)
            models = [m["name"] for m in r.json().get("models", [])]
            lines.append(f"Ollama:  ✅ Running")
            lines.append(f"Models:  {', '.join(models) if models else 'none'}")
        except Exception:
            lines.append("Ollama:  ❌ Offline")

        # Memory
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            lines.append(f"Disk:    {free // 2**30}GB free / {total // 2**30}GB")
        except Exception:
            pass

        # Uptime
        try:
            with open("/proc/uptime") as f:
                uptime_s = float(f.read().split()[0])
            h, m = divmod(int(uptime_s) // 60, 60)
            lines.append(f"Uptime:  {h}h {m}m")
        except Exception:
            pass

        # Camera
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            lines.append(f"Camera:  {'✅ /dev/video0' if cap.isOpened() else '❌ Not found'}")
            cap.release()
        except Exception:
            lines.append("Camera:  ❓ Unknown")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /search  — web search
    # ------------------------------------------------------------------

    async def _handle_search(self, update, context):
        if not self._auth_check(str(update.effective_user.id)):
            await update.message.reply_text("Not authorized.")
            return

        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /search <query>")
            return

        await update.message.reply_text(f"🔍 Searching: {query}…")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._do_search, query)
        await update.message.reply_text(result[:4000])

    def _do_search(self, query: str) -> str:
        try:
            from src.web_search import WebSearch
            ws = WebSearch({})
            return ws.search_and_format(query, max_results=5)
        except Exception as e:
            log.error("Search failed: %s", e)
            return f"Search unavailable: {e}"

    # ------------------------------------------------------------------
    # /memory  — search conversation history
    # ------------------------------------------------------------------

    async def _handle_memory(self, update, context):
        if not self._auth_check(str(update.effective_user.id)):
            await update.message.reply_text("Not authorized.")
            return

        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /memory <search term>")
            return

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._do_memory_search, query)
        await update.message.reply_text(result[:4000])

    def _do_memory_search(self, query: str) -> str:
        try:
            from src.database import DatabaseManager
            db = DatabaseManager("~/.local/share/talking-llm/assistant.db")
            db.init_db()
            results = db.semantic_search_memories(query, limit=5)
            if not results:
                return f"No memories found for: {query}"
            lines = [f"🧠 Memory results for '{query}':\n"]
            for r in results:
                lines.append(f"• {r['key']}: {r['value']}")
            return "\n".join(lines)
        except Exception as e:
            log.error("Memory search failed: %s", e)
            return f"Memory search unavailable: {e}"

    # ------------------------------------------------------------------
    # Regular text → LLM via bus
    # ------------------------------------------------------------------

    async def _handle_message(self, update, context):
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        message_text = update.message.text or ""

        if not self._auth_check(str(user.id)):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        if self._is_rate_limited(str(user.id)):
            await update.message.reply_text(
                f"Too many messages. Limit: {_RATE_LIMIT_MESSAGES} per minute."
            )
            return

        if len(message_text) > _MAX_MESSAGE_LENGTH:
            await update.message.reply_text(f"Message too long (max {_MAX_MESSAGE_LENGTH} chars).")
            return

        log.info("Message from user %s (len=%d)", user.id, len(message_text))

        self.bus.publish_inbound(InboundMessage(
            channel="telegram",
            sender_id=str(user.id),
            chat_id=chat_id,
            content=message_text,
            session_key=f"telegram:{chat_id}",
            timestamp=time.time(),
            metadata={"username": user.username},
        ))
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def create_telegram_channel(bus: MessageBus, config: dict) -> Optional[TelegramChannel]:
    """Create a Telegram channel from config."""
    if not config.get("enabled", False):
        return None

    token = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("token", "")
    allowed_users = config.get("allow_from", [])

    if not token:
        log.warning("Telegram bot token not configured")
        return None

    return TelegramChannel(bus, token, allowed_users)
