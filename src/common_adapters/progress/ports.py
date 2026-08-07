"""
Progress Publisher Ports

Protocol and utility classes for progress publishing.
"""

from __future__ import annotations

from typing import Protocol

from .models import ProgressEvent


class ProgressPublisher(Protocol):
    """Protocol for progress event publishers."""
    
    async def publish(self, event: ProgressEvent) -> None:
        """Publish a progress event to the configured transport."""


class NullProgressPublisher:
    """No-op publisher for testing or when progress is disabled."""
    
    async def publish(self, event: ProgressEvent) -> None:
        _ = event


class CompositeProgressPublisher:
    """Publishes to multiple backends simultaneously."""
    
    def __init__(self, publishers: list[ProgressPublisher]):
        self._publishers = publishers

    async def publish(self, event: ProgressEvent) -> None:
        for publisher in self._publishers:
            await publisher.publish(event)
