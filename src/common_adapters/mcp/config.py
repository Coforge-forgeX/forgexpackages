"""
MCP Client Configuration

Standardized configuration for building FastMCP clients.
Supports timeouts, auth, roots, and extra kwargs.

Agent decides configuration and passes explicit values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


# Convention: MCPConfig has top-level "mcpServers" for multi-server mode
MCPConfig = dict[str, Any]


@dataclass(frozen=True)
class ClientBuildOptions:
    """
    Options for constructing a FastMCP Client in a consistent way.

    Parameters
    ----------
    timeout_s:
        Default request timeout passed to fastmcp.Client.
    init_timeout_s:
        Timeout for initial connection/initialize handshake. Set to 0 to disable.
    roots:
        Either a static list of filesystem roots or a roots handler callback.
        Used to tell servers what local resources the client can access.
    auth:
        For HTTP transports: can be "oauth", a bearer token string, or an auth helper
        object (OAuth/BearerAuth) that implements httpx.Auth.
    extra:
        Escape hatch for any extra keyword args supported by fastmcp.Client.
    """

    timeout_s: Optional[float] = 30.0
    init_timeout_s: Optional[float] = None
    roots: Any = None
    auth: Any = None
    extra: Mapping[str, Any] = field(default_factory=dict)


def is_mcp_config(obj: Any) -> bool:
    """
    Detect whether `obj` looks like an MCPConfig dictionary.

    FastMCP supports creating a client from a config dict that includes
    `mcpServers`, enabling multi-server usage with namespaced tool names.
    """
    return isinstance(obj, dict) and "mcpServers" in obj


@dataclass
class MCPSettings:
    """
    MCP-specific settings container.
    
    Agent creates this with explicit values.
    """

    # MCP Server URLs
    mcp_jira_url: str = ""
    mcp_ado_url: str = ""
    mcp_default_url: str = ""

    # Timeouts
    mcp_timeout_s: float = 30.0
    mcp_init_timeout_s: Optional[float] = None

    # Cache TTL
    mcp_cache_ttl_s: float = 180.0

    # Auth (optional)
    mcp_auth_token: str = ""
    mcp_subscription_key: str = ""

    def get_default_options(self) -> ClientBuildOptions:
        """Get ClientBuildOptions from these settings."""
        auth = None
        if self.mcp_auth_token:
            auth = self.mcp_auth_token

        return ClientBuildOptions(
            timeout_s=self.mcp_timeout_s,
            init_timeout_s=self.mcp_init_timeout_s,
            auth=auth,
        )
