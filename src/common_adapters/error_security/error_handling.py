"""
Reusable error handling utilities for production agents.
"""

import asyncio
import logging
import random
import re
import time
from dataclasses import dataclass, field
from functools import wraps
from http import HTTPStatus
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ErrorContext:
    """Normalized reusable error payload."""

    message: str
    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"
    details: dict[str, Any] = field(default_factory=dict)
    category: str = "server_error"
    retryable: bool = False


class ApplicationError(Exception):
    """Reusable transport-agnostic application exception."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        error_code: str | None = None,
        details: Optional[dict[str, Any]] = None,
        retryable: bool | None = None,
    ):
        self.context = ErrorContext(
            message=message,
            status_code=status_code,
            error_code=error_code or _default_error_code(status_code),
            details=details or {},
            category=_status_category(status_code),
            retryable=_is_retryable(status_code) if retryable is None else retryable,
        )
        super().__init__(message)


def _status_category(status_code: int) -> str:
    if 400 <= status_code < 500:
        return "client_error"
    if status_code >= 500:
        return "server_error"
    return "unknown"


def _is_retryable(status_code: int) -> bool:
    return status_code in {408, 425, 429} or status_code >= 500


def _default_error_code(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return "INTERNAL_SERVER_ERROR"


def normalize_exception(exc: Exception) -> ErrorContext:
    """Convert arbitrary exceptions into a reusable error context."""

    if isinstance(exc, ApplicationError):
        return exc.context

    status_code = getattr(exc, "status_code", 500)
    details = getattr(exc, "details", {}) or {}
    error_code = getattr(exc, "error_code", _default_error_code(status_code))
    message = getattr(exc, "message", None) or sanitize_exception_text(exc)

    return ErrorContext(
        message=message,
        status_code=status_code,
        error_code=error_code,
        details=details,
        category=_status_category(status_code),
        retryable=_is_retryable(status_code),
    )

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


def build_api_error_payload(
    exc: Exception,
    *,
    correlation_id: str | None = None,
    include_details: bool = True,
) -> dict[str, Any]:
    """Create consistent API-safe error payloads for 4xx/5xx responses."""

    context = normalize_exception(exc)
    payload: dict[str, Any] = {
        "success": False,
        "error": context.error_code,
        "message": context.message,
        "status_code": context.status_code,
        "category": context.category,
        "retryable": context.retryable,
    }

    if include_details and context.details:
        payload["details"] = context.details

    if correlation_id:
        payload["correlation_id"] = correlation_id

    return payload


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
