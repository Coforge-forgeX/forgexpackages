"""
Common Adapters - Shared adapter library for AI agents

This package provides cloud-agnostic adapters and utilities for:
- Cloud provider abstraction (Azure, AWS, Local)
- Push notifications via WebSocket
- Progress reporting with multiple backends
- MCP client framework
- And more...
"""

from . import cloud
from . import notifications
from . import progress
from . import mcp

__all__ = [
    "cloud",
    "notifications", 
    "progress",
    "mcp",
]
