"""Structured logging with rotating file handler and console output."""

import logging
import os
from logging.handlers import RotatingFileHandler

_DEFAULT_LOG_DIR = os.path.expanduser("~/.local/share/talking-llm/logs")
_LOG_FILE = "assistant.log"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3


def setup_logging(
    level: str = "INFO",
    log_dir: str | None = None,
) -> None:
    """Configure root logger with rotating file + console handlers.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR).
        log_dir: Directory for log files. Defaults to ~/.local/share/talking-llm/logs.
    """
    log_dir = log_dir or _DEFAULT_LOG_DIR
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, _LOG_FILE)
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid duplicate handlers on repeated calls
    if root.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler
    fh = RotatingFileHandler(
        log_path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT
    )
    fh.setLevel(numeric_level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler (typically INFO or higher)
    ch = logging.StreamHandler()
    ch.setLevel(numeric_level)
    ch.setFormatter(fmt)
    root.addHandler(ch)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
