"""Retry decorator with exponential backoff for transient failures."""

import functools
import time

from src.logging_config import get_logger

log = get_logger(__name__)


def retry_on_exception(
    max_retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Decorator that retries a function on specified exceptions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts after the initial call.
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay cap in seconds.
        retryable_exceptions: Tuple of exception types to retry on.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        log.warning(
                            "%s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            func.__qualname__, attempt + 1, max_retries + 1, e, delay,
                        )
                        time.sleep(delay)
                    else:
                        log.error(
                            "%s failed after %d attempts: %s",
                            func.__qualname__, max_retries + 1, e,
                        )
            raise last_exc
        return wrapper
    return decorator
