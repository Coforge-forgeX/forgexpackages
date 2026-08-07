"""
MCP Client Manager Framework

High-level wrapper around FastMCP Client providing:
- Async context lifecycle management
- Tool caching with TTL + server notification invalidation
- Composable call interceptors for tracing/retry/metrics
- Handler adapters for log/progress/sampling/elicitation

Agent creates client with explicit configuration.
"""

from .client import MCPAppClient, call_mcp_tool
from .config import ClientBuildOptions, MCPConfig, MCPSettings, is_mcp_config
from .cache import ToolCache
from .factory import ClientFactory
from .handlers import (
    LogHandler,
    ProgressHandler,
    SamplingHandler,
    ElicitationHandler,
    DefaultLogAdapter,
    DefaultProgressAdapter,
    DefaultSamplingAdapter,
    DefaultElicitationAdapter,
    ToolCacheInvalidationHandler,
    LLMProvider,
)
from .interceptors import (
    CallInterceptor,
    CompositeInterceptor,
    LoggingInterceptor,
    MetricsInterceptor,
)

__all__ = [
    # Main client
    "MCPAppClient",
    "call_mcp_tool",
    # Configuration
    "ClientBuildOptions",
    "MCPConfig",
    "MCPSettings",
    "is_mcp_config",
    # Cache
    "ToolCache",
    # Factory
    "ClientFactory",
    # Handlers
    "LogHandler",
    "ProgressHandler",
    "SamplingHandler",
    "ElicitationHandler",
    "DefaultLogAdapter",
    "DefaultProgressAdapter",
    "DefaultSamplingAdapter",
    "DefaultElicitationAdapter",
    "ToolCacheInvalidationHandler",
    "LLMProvider",
    # Interceptors
    "CallInterceptor",
    "CompositeInterceptor",
    "LoggingInterceptor",
    "MetricsInterceptor",
]
