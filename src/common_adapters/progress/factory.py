"""
Progress Reporter Factory

Helper function to create configured ProgressReporter instances.
Agent provides the publisher explicitly.
"""

from __future__ import annotations

from typing import Any

from .ports import ProgressPublisher
from .reporter import ProgressReporter


def create_progress_reporter(
    publisher: ProgressPublisher,
    *,
    operation: str,
    user_id: str,
    conversation_id: str | None = None,
    job_id: str | None = None,
    correlation_id: str | None = None,
    provider: str = "agent",
    payload: Any = None,
    req: Any = None,
) -> ProgressReporter:
    """
    Create a configured ProgressReporter.
    
    Args:
        publisher: The ProgressPublisher to use for publishing events
        operation: Name of the operation being tracked
        user_id: User ID for the operation
        conversation_id: Optional conversation ID
        job_id: Optional job ID
        correlation_id: Optional correlation ID (extracted from req if not provided)
        provider: Provider name for the event
        payload: Optional payload object to extract conversation_id/job_id from
        req: Optional request object to extract correlation_id from headers
        
    Returns:
        Configured ProgressReporter instance
    """
    # Extract correlation_id from request headers if not provided
    if correlation_id is None and req is not None:
        if hasattr(req, "headers"):
            correlation_id = req.headers.get("x-correlation-id") or req.headers.get("X-Correlation-ID")

    # Extract conversation_id and job_id from payload if not provided
    if payload is not None:
        if conversation_id is None:
            conv_id = getattr(payload, "conversation_id", None)
            if conv_id:
                conversation_id = str(conv_id)
        if job_id is None:
            j_id = getattr(payload, "job_id", None)
            if j_id:
                job_id = str(j_id)

    return ProgressReporter(
        publisher,
        operation=operation,
        user_id=str(user_id),
        conversation_id=conversation_id,
        job_id=job_id,
        correlation_id=correlation_id,
        provider=provider,
    )
