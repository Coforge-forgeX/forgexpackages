from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CancelledError(RuntimeError):
    """Raised when a request was cancelled by the caller."""


@dataclass(frozen=True)
class CancelRequest:
    job_id: Optional[str] = None
    conversation_id: Optional[str] = None
    workspace_id: Optional[str] = None
    user_id: Optional[str] = None
    reason: str = "user_requested"


class SessionTerminatedError(RuntimeError):
    """Raised when a conversation/session has been terminated."""


def _cancellation_key(*, job_id: Optional[str], conversation_id: Optional[str]) -> str:
    if job_id:
        return f"job:{job_id}"
    if conversation_id:
        return f"conv:{conversation_id}"
    raise ValueError("Either job_id or conversation_id is required")


class _CancellationStore:
    """Best-effort cancellation store.

    Primary: Redis via `common_adapters.cache.CacheFactory`.
    Fallback: in-memory map (process-local only).
    """

    def __init__(self, *, prefix: str = "cancel:") -> None:
        self._prefix = prefix
        self._cache = None
        self._lock = threading.Lock()
        self._mem: dict[str, dict[str, Any]] = {}

        # Separate session termination flag store. Termination is sticky for the
        # process lifetime unless explicitly cleared.
        self._terminated: dict[str, dict[str, Any]] = {}

    def _get_cache(self):
        if self._cache is not None:
            return self._cache
        try:
            from common_adapters.cache import CacheFactory

            CacheFactory.initialize()
            self._cache = CacheFactory.get_cache(prefix=self._prefix)
        except Exception:
            self._cache = None
        return self._cache

    def _disable_cache(self) -> None:
        # If Redis is misconfigured/unreachable, fall back to in-memory for the
        # rest of the process lifetime.
        self._cache = None

    async def mark_cancelled(self, key: str, req: CancelRequest) -> None:
        payload = {
            **asdict(req),
            "key": key,
            "cancelled": True,
            "ts": time.time(),
        }

        cache = self._get_cache()
        if cache is not None:
            try:
                await cache.store_data({key: json.dumps(payload)})
                # Ensure cancellation doesn't poison subsequent requests forever.
                # CacheFactory-backed caches are typically Redis-based; if they support
                # expiry via their own defaults, this is still fine.
                return
            except Exception:
                # Redis misconfigured/unreachable at runtime.
                self._disable_cache()

        # Fallback: process-local cancellation.
        with self._lock:
            self._mem[self._prefix + key] = payload

    async def is_cancelled(self, key: str) -> bool:
        # AZURE FIX: Check Redis first for multi-worker scenarios
        # The 15-second TTL prevents poisoning subsequent requests in the same conversation
        cache = self._get_cache()
        if cache is not None:
            try:
                logger.info(f"[CANCEL_CHECK] Checking Redis for cancellation key: {key}")
                result = await cache.retrieve_data(key)
                if result and result.get("status") == "success":
                    data = result.get("data", {})
                    cached = data.get(key)
                    if cached:
                        import json as _json
                        payload = _json.loads(cached) if isinstance(cached, str) else cached
                        ts = float(payload.get("ts") or 0)
                        if ts and (time.time() - ts) <= _CANCEL_TTL_SECONDS:
                            # Found active cancellation in Redis - return True
                            logger.info(f"[CANCEL_CHECK] ✅ CANCELLED - Found active cancellation in Redis for key: {key}")
                            return True
                        else:
                            logger.info(f"[CANCEL_CHECK] Found in Redis but EXPIRED (age: {time.time() - ts:.1f}s, TTL: {_CANCEL_TTL_SECONDS}s)")
                    else:
                        logger.info(f"[CANCEL_CHECK] Key {key} not found in Redis data")
                else:
                    logger.info(f"[CANCEL_CHECK] Redis retrieve returned: {result}")
            except Exception as e:
                # Fall back to local memory on Redis errors
                logger.error(f"[CANCEL_CHECK] Redis error for key {key}: {e}")
        else:
            logger.warning(f"[CANCEL_CHECK] ⚠️ Redis cache is None - using local memory only (multi-worker cancellation will NOT work!)")

        # Fallback: Process-local check (works for single-worker / local dev)
        with self._lock:
            payload = self._mem.get(self._prefix + key)
            if not payload:
                logger.info(f"[CANCEL_CHECK] Key {key} not found in local memory either")
                return False
            ts = float(payload.get("ts") or 0)
            if ts and (time.time() - ts) > _CANCEL_TTL_SECONDS:
                self._mem.pop(self._prefix + key, None)
                logger.info(f"[CANCEL_CHECK] Found in local memory but EXPIRED")
                return False
            logger.info(f"[CANCEL_CHECK] ✅ CANCELLED - Found in local memory for key: {key}")
            return True

    def clear_cancelled(self, key: str) -> None:
        """Clear a cancellation flag immediately (process-local only)."""
        with self._lock:
            self._mem.pop(self._prefix + key, None)

    def mark_terminated(self, conversation_id: str, req: dict[str, Any]) -> None:
        """Mark a conversation as terminated (sticky, process-local)."""
        with self._lock:
            self._terminated[f"conv:{conversation_id}"] = {**req, "terminated": True, "ts": time.time()}

    def is_terminated(self, conversation_id: str) -> bool:
        with self._lock:
            return f"conv:{conversation_id}" in self._terminated

    def clear_terminated(self, conversation_id: str) -> None:
        with self._lock:
            self._terminated.pop(f"conv:{conversation_id}", None)


_store = _CancellationStore()

# How long a cancellation stays active for a conversation/job.
# This should be short: it exists only to stop the currently running request.
_CANCEL_TTL_SECONDS = 15


def _run_coroutine_sync(coro) -> Any:
    """Run an async coroutine from sync code.

    If we're already in an event loop, run it in a temporary thread so we still
    get completion semantics (important for immediate cancel visibility).
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    out: dict[str, Any] = {}

    def _worker():
        out["value"] = asyncio.run(coro)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=5)
    return out.get("value")


def _mem_key(cancellation_key: str) -> str:
    # Avoid depending on Redis/cache prefixing behavior. We keep in-memory keys
    # fully qualified with the store prefix so reads/writes match.
    return f"{_store._prefix}{cancellation_key}"


class CancellationToken:
    """Process-local fast path cancellation token."""

    __slots__ = ("_evt", "created_at", "key", "_task")

    def __init__(self, key: str) -> None:
        self._evt = threading.Event()
        self.created_at = time.time()
        self.key = key
        self._task = None

    def cancel(self) -> None:
        self._evt.set()

    def is_cancelled(self) -> bool:
        return self._evt.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancelledError("cancelled")


_tok_lock = threading.Lock()
_tokens: dict[str, CancellationToken] = {}


def _cancel_sync_task(tok: "CancellationToken") -> None:
    """Best-effort attempt to interrupt a running sync provider call.

    Some providers (notably AzureOpenAIProvider) execute a blocking HTTP request
    inside `run_in_executor`. That future can be cancelled by cancelling the
    asyncio Task that is awaiting it.
    """

    t = getattr(tok, "_task", None)
    try:
        if t is not None:
            t.cancel()
    except Exception:
        pass


def register_cancellation(*, job_id: Optional[str] = None, conversation_id: Optional[str] = None) -> CancellationToken:
    key = _cancellation_key(job_id=job_id, conversation_id=conversation_id)
    tok = CancellationToken(key)
    with _tok_lock:
        _tokens[key] = tok
    return tok


def register_task(
    *,
    job_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    task: Any,
) -> None:
    """Associate an asyncio Task with a cancellation key.

    When `cancel_conversation` is called, we cancel this task as well. This is
    the only reliable way to stop in-flight awaits (e.g., run_in_executor)
    without requiring the provider implementation to be cancellation-aware.
    """

    key = _cancellation_key(job_id=job_id, conversation_id=conversation_id)

    # ALWAYS create a fresh token for each new request to avoid state leaks
    tok = CancellationToken(key)

    with _tok_lock:
        # Remove any old token first (from previous request with same conversation_id)
        old_tok = _tokens.pop(key, None)
        if old_tok:
            logger.info(f"[REGISTER_TASK] Replacing old token for key {key}")

        # Register the new token
        _tokens[key] = tok

        # Check for stale cancellation flags from previous requests
        with _store._lock:
            payload = _store._mem.get(_mem_key(key))
            ts = float((payload or {}).get("ts") or 0)
            recently_cancelled = bool(payload) and (not ts or (time.time() - ts) <= _CANCEL_TTL_SECONDS)

        if recently_cancelled:
            # This is likely a stale flag from a previous request - clear it!
            logger.warning(f"[REGISTER_TASK] Found stale cancellation flag for key {key}, clearing it")
            with _store._lock:
                _store._mem.pop(_mem_key(key), None)
            # Don't cancel this NEW task - it's a fresh request!

        # Associate the task with the token
        tok._task = task
        logger.info(f"[REGISTER_TASK] Registered task for key {key}")


def unregister_task(*, job_id: Optional[str] = None, conversation_id: Optional[str] = None) -> None:
    key = _cancellation_key(job_id=job_id, conversation_id=conversation_id)
    with _tok_lock:
        tok = _tokens.pop(key, None)  # Use pop to ensure removal
        if tok is not None:
            try:
                tok._task = None
                # Clear the token's internal state
                tok._evt.clear()
            except Exception as e:
                logger.warning(f"[UNREGISTER_TASK] Error clearing token for key {key}: {e}")
        logger.info(f"[UNREGISTER_TASK] Unregistered task for key {key}")


def unregister_cancellation(*, job_id: Optional[str] = None, conversation_id: Optional[str] = None) -> None:
    key = _cancellation_key(job_id=job_id, conversation_id=conversation_id)
    with _tok_lock:
        _tokens.pop(key, None)


async def is_cancelled(*, job_id: Optional[str] = None, conversation_id: Optional[str] = None) -> bool:
    key = _cancellation_key(job_id=job_id, conversation_id=conversation_id)
    # Token cancellation is for interrupting the currently running Task.
    # It must NOT poison future requests, so do not treat token state as a
    # persistent cancelled flag.
    # Also check process-local store (covers cases where Redis is down).
    with _store._lock:
        payload = _store._mem.get(_mem_key(key))
        if payload:
            ts = float(payload.get("ts") or 0)
            if ts and (time.time() - ts) <= _CANCEL_TTL_SECONDS:
                return True
            # expired -> clean it up
            _store._mem.pop(_mem_key(key), None)
    return await _store.is_cancelled(key)


def terminate_session(
    *,
    conversation_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    reason: str = "user_requested",
) -> dict:
    """Terminate a conversation/session.

    This is distinct from request cancellation.
    Termination is sticky and can be used by agents/orchestrators to stop
    persisting outputs for the rest of the conversation.
    """
    payload = {
        "status": "success",
        "terminated": True,
        "conversation_id": str(conversation_id),
        "workspace_id": workspace_id,
        "user_id": user_id,
        "reason": reason,
    }
    _store.mark_terminated(str(conversation_id), payload)
    return payload


def is_session_terminated(*, conversation_id: str) -> bool:
    return _store.is_terminated(str(conversation_id))


def raise_if_session_terminated(*, conversation_id: str) -> None:
    if is_session_terminated(conversation_id=str(conversation_id)):
        raise SessionTerminatedError("session_terminated")


def cancel_conversation(
    *,
    job_id: str | None = None,
    conversation_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
    reason: str = "user_requested",
) -> dict:
    """MCP tool entrypoint (sync).

    Writes cancellation to the shared store (Redis if configured) and also cancels
    any in-process token for immediate stop.
    """

    key = _cancellation_key(job_id=job_id, conversation_id=conversation_id)
    # Cancel any in-flight asyncio Task registered for this key.
    # This is the mechanism that actually interrupts the ongoing await.
    with _tok_lock:
        tok = _tokens.get(key)
        if tok:
            # Cancel the in-flight asyncio Task (if registered)
            _cancel_sync_task(tok)
        # If tok is missing, cancellation may have arrived before the first
        # register_task(). That's fine; we still set the short-lived flag below
        # so polling-based checks stop the pipeline.

    # Ensure a short-lived "cancelled" flag exists (TTL-based) so callers that
    # poll `is_cancelled()` can stop quickly.

    req = CancelRequest(
        job_id=job_id,
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        user_id=user_id,
        reason=reason,
    )

    # Persisting cancellation to a shared store is useful for multi-process setups,
    # but it also risks poisoning an entire conversation (same conversation_id) if
    # the client reuses the conversation_id for subsequent prompts.
    #
    # For BA/UI semantics, cancellation is intended to stop ONLY the in-flight
    # request. We therefore keep cancellation process-local and short-lived.
    with _store._lock:
        _store._mem[_mem_key(key)] = {"cancelled": True, "ts": time.time(), "key": key}

    # Do NOT create/persist a token here. Tokens are only for holding the
    # currently running asyncio task (if any). Creating tokens during cancel
    # causes subsequent requests (same conversation_id) to potentially inherit
    # stale state.

    # Auto-clear so subsequent prompts in the same conversation work normally.
    def _clear_later():
        time.sleep(_CANCEL_TTL_SECONDS)
        with _store._lock:
            _store._mem.pop(_mem_key(key), None)

    threading.Thread(target=_clear_later, daemon=True).start()

    return {
        "status": "success",
        "cancelled": True,
        "key": key,
        "job_id": job_id,
        "conversation_id": conversation_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "reason": reason,
    }


def clear_cancellation(*, job_id: str | None = None, conversation_id: str | None = None) -> None:
    """Clear a cancellation flag immediately.

    This is intended for systems that reuse conversation_id across turns: after the
    in-flight task is cancelled, clearing prevents subsequent requests from being
    affected within the TTL window.
    """
    key = _cancellation_key(job_id=job_id, conversation_id=conversation_id)
    _store.clear_cancelled(key)
