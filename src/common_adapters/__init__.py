"""
Common Adapters - Shared adapter library for AI agents

This package provides cloud-agnostic adapters and utilities for:
- Cloud provider abstraction (Azure, AWS, GCP, Local)
- Push notifications via WebSocket
- Progress reporting with multiple backends
- MCP client framework
- Unified WebSocket relay for Service Bus
- And more...

Import behavior:
This package intentionally avoids importing subpackages at module import time.
Many subpackages depend on optional third-party libraries; eager imports would
break lightweight consumers that only need a small utility.

Use explicit imports such as:
- `from common_adapters.context_compaction.compactor import ContextCompactor`
- `from common_adapters.input_validation import is_valid_user_prompt`
"""

__all__ = [
    "cloud",
    "notifications", 
    "progress",
    "mcp",
    "relay",
    "input_validation",
]
