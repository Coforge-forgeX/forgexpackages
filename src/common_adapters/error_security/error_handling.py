"""
Reusable error handling utilities for production agents.
"""

import asyncio
import logging
import random
import re
import time
from functools import wraps
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-._~+/]+=*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(access[_\- ]?token|api[_\- ]?key|secret|password)\b\s*[:=]\s*['\"]?([^\s,'\"]+)"), r"\1=[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL REDACTED]"),
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE REDACTED]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN REDACTED]"),
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CARD REDACTED]"),
]


def sanitize_exception_text(exc: Exception, max_len: int = 500) -> str:
    """Return a redacted exception string safe for metadata and user-visible messages."""
    text = str(exc or "")
    original = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    if text != original:
        logger.warning("[ErrorHandling] Sensitive values redacted in exception text")
    return text[:max_len]


def build_error_response(
    *,
    title: str,
    user_message: str,
    exception: Optional[Exception] = None,
    metadata: Optional[dict] = None,
    request_id: Optional[str] = None,
) -> dict:
    """Build a consistent error response payload."""
    error_text = sanitize_exception_text(exception) if exception else None
    logger.error(
        "[ErrorHandling] Building error response title=%s request_id=%s error_type=%s issue=%s",
        title,
        request_id,
        type(exception).__name__ if exception else None,
        error_text,
    )
    content = f"# {title}\n\n{user_message}"
    if error_text:
        content += f"\n\n**Issue:** {error_text}"
    if request_id:
        content += f"\n\n**Reference ID:** `{request_id}`"

    response_metadata = dict(metadata or {})
    response_metadata["error"] = True
    if exception:
        response_metadata["error_type"] = type(exception).__name__
        response_metadata["exception"] = error_text
    if request_id:
        response_metadata["request_id"] = request_id

    return {
        "content": content,
        "metadata": response_metadata,
    }


async def async_with_retry(
    operation_name: str,
    operation: Callable[[], Awaitable[Any]],
    *,
    max_retries: int = 2,
    base_delay_sec: float = 1.0,
    max_delay_sec: float = 10.0,
    log: Optional[logging.Logger] = None,
) -> Any:
    """Execute an async operation with bounded exponential backoff and jitter."""
    active_logger = log or logger
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            if attempt == 0:
                active_logger.info(
                    "[%s] starting operation max_retries=%s",
                    operation_name,
                    max_retries,
                )
            return await operation()
        except Exception as exc:  # pragma: no cover - pass-through retry behavior
            last_exc = exc
            if attempt >= max_retries:
                break
            delay = min(base_delay_sec * (2 ** attempt), max_delay_sec)
            delay = delay * (0.75 + random.random() * 0.5)
            active_logger.warning(
                "[%s] failed (%s/%s): %s; retrying in %.2fs",
                operation_name,
                attempt + 1,
                max_retries + 1,
                sanitize_exception_text(exc),
                delay,
            )
            await asyncio.sleep(delay)

    active_logger.error(
        "[%s] failed after %s attempts: %s",
        operation_name,
        max_retries + 1,
        sanitize_exception_text(last_exc or Exception("unknown error")),
    )
    raise last_exc  # type: ignore[misc]


# Backward-compatible sync decorator retained for callers that still rely on it.
def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
):
    """Retry decorator with exponential backoff for sync functions."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        delay = delay * (0.5 + random.random())
                        time.sleep(delay)
            raise last_exception

        return wrapper

    return decorator
