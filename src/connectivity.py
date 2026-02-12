"""Internet connectivity monitor with background checking."""

import threading
import time

import requests

from src.logging_config import get_logger

log = get_logger(__name__)


class ConnectivityMonitor:
    """Monitors internet connectivity in a background thread."""

    def __init__(self, check_url: str = "https://openrouter.ai", interval: int = 300):
        self.check_url = check_url
        self.interval = interval
        self.is_online = False
        self._lock = threading.Lock()
        self._callbacks: list = []
        self._thread: threading.Thread | None = None

    def check_now(self) -> bool:
        """Synchronous connectivity check (HEAD request, 3s timeout)."""
        try:
            resp = requests.head(self.check_url, timeout=3, allow_redirects=True)
            online = resp.status_code < 500
        except (requests.ConnectionError, requests.Timeout, OSError):
            online = False

        with self._lock:
            changed = self.is_online != online
            self.is_online = online

        if changed:
            log.info("Connectivity changed: %s", "online" if online else "offline")
            for cb in self._callbacks:
                try:
                    cb(online)
                except Exception:
                    pass

        return online

    def on_status_change(self, callback):
        """Register a callback(is_online: bool) for connectivity changes."""
        self._callbacks.append(callback)

    def start(self):
        """Start background monitoring daemon thread."""
        self.check_now()  # Initial check
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while True:
            time.sleep(self.interval)
            self.check_now()
