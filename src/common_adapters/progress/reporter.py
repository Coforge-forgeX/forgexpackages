"""
Progress Reporter

High-level helper for standardizing progress event emission.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict

from .models import ProgressEvent
from .ports import ProgressPublisher

logger = logging.getLogger("common_adapters.progress.reporter")


class ProgressReporter:
    """Use-case level helper to standardize progress events."""

    def __init__(
        self,
        publisher: ProgressPublisher,
        *,
        operation: str,
        user_id: str,
        conversation_id: str | None,
        job_id: str | None,
        correlation_id: str | None,
        provider: str = "agent",
    ):
        self._publisher = publisher
        self._operation = operation
        self._user_id = user_id
        self._conversation_id = conversation_id
        self._job_id = job_id
        self._correlation_id = correlation_id
        self._provider = provider

        self._event_seq = 0
        self._last_progress = 0
        self._emit_lock = asyncio.Lock()
        self._run_id = uuid.uuid4().hex

    @property
    def run_id(self) -> str:
        """Get the unique run ID for this reporter instance."""
        return self._run_id

    @property
    def event_seq(self) -> int:
        """Get the current event sequence number."""
        return self._event_seq

    async def emit(
        self, 
        *, 
        status: str, 
        message: str, 
        metadata: Dict[str, Any] | None = None
    ) -> bool:
        """
        Emit a progress event.
        
        Args:
            status: Status string (e.g., "in_progress", "completed", "failed")
            message: Human-readable progress message
            metadata: Additional metadata to include
            
        Returns:
            True if published successfully, False otherwise
        """
        async with self._emit_lock:
            payload = dict(metadata or {})
            current_progress = int(payload.get("progress_percent", self._last_progress))
            if current_progress < self._last_progress:
                current_progress = self._last_progress
            self._last_progress = current_progress

            self._event_seq += 1
            payload["progress_percent"] = current_progress
            payload["run_id"] = self._run_id
            payload["event_seq"] = self._event_seq

            event = ProgressEvent(
                operation=self._operation,
                status=status,
                message=message,
                user_id=self._user_id,
                conversation_id=self._conversation_id,
                job_id=self._job_id,
                correlation_id=self._correlation_id,
                provider=self._provider,
                metadata=payload,
            )
            try:
                await self._publisher.publish(event)
                return True
            except Exception as exc:
                logger.error(
                    "Progress publish failed: operation=%s status=%s user_id=%s error=%s",
                    self._operation,
                    status,
                    self._user_id,
                    exc,
                )
                return False

    async def start(self, message: str = "Starting operation") -> bool:
        """Emit a start event."""
        return await self.emit(
            status="started",
            message=message,
            metadata={"progress_percent": 0},
        )

    async def progress(
        self, 
        message: str, 
        percent: int | None = None,
        **extra_metadata,
    ) -> bool:
        """Emit a progress update."""
        metadata = dict(extra_metadata)
        if percent is not None:
            metadata["progress_percent"] = percent
        return await self.emit(
            status="in_progress",
            message=message,
            metadata=metadata,
        )

    async def complete(self, message: str = "Operation completed") -> bool:
        """Emit a completion event."""
        return await self.emit(
            status="completed",
            message=message,
            metadata={"progress_percent": 100},
        )

    async def fail(self, message: str, error: Exception | None = None) -> bool:
        """Emit a failure event."""
        metadata = {}
        if error:
            metadata["error_type"] = type(error).__name__
            metadata["error_message"] = str(error)
        return await self.emit(
            status="failed",
            message=message,
            metadata=metadata,
        )
