"""
langfuse_instrumentation
========================

Shared auto-instrumentation package for Langfuse tracing across all ForgeX agents.

Traces with full span details:
  1. FastMCP tools           (user_id / session_id / workspace_id metadata)
  2. AzureCustomLLM          (LangChain CallbackHandler — token usage, prompt, completion)
  3. AzureChatOpenAI bare    (jira_agent / ado_agent)
  4. LangGraph graphs        (all nodes, tool calls, LLM generations)
  5. LightRAG RAG queries    (namespace, prompt, context, latency)
  6. MCP sub-agent calls     (outbound call_tool spans)

Usage:
    from langfuse_instrumentation import setup_langfuse, flush, is_enabled
"""

from .instrumentation import (
    setup_langfuse,
    get_langfuse,
    get_handler,
    is_enabled,
    flush,
    ensure_trace_user_context,
)

__all__ = [
    "setup_langfuse",
    "get_langfuse",
    "get_handler",
    "is_enabled",
    "flush",
    "ensure_trace_user_context",
]

__version__ = "0.1.0"
