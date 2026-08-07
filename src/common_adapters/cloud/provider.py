"""
Cloud Provider Enum

Simple enum for supported cloud providers.
Agent decides which provider to use and passes it to adapters.
"""

from __future__ import annotations

from enum import Enum


class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AZURE = "azure"
    AWS = "aws"
    LOCAL = "local"

    @classmethod
    def parse(cls, value: str) -> "CloudProvider":
        """
        Parse a string into CloudProvider enum.
        
        Args:
            value: Provider string (azure, aws, local) - case insensitive
            
        Returns:
            CloudProvider enum value, defaults to LOCAL if invalid
        """
        normalized = value.strip().lower() if value else ""
        if normalized in {"azure", "aws", "local"}:
            return cls(normalized)
        return cls.LOCAL
