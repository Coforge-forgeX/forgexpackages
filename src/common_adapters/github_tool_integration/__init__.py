"""
GitHub Tool Integration Package

This package provides GitHub integration tools for multi-agent systems.
Import the main classes directly from this package across all agents.

Usage:
    from common_adapters.github_tool_integration import (
        GitHubLLMWrapper, 
        GitHubClientManagerAsync,
        get_github_tools,
        github_prompts
    )
"""

from .github_client_for_llm import GitHubLLMWrapper, agent_tool
from .github_client_manager import GitHubClientManagerAsync
from .github_prompts import github_prompts
from .github_tools import get_github_tools
from .github_graph import (
    ReactGraphState,
    Context,
    create_github_graph_with_history,
    create_github_graph_simple
)
from .github_connection import (
    test_github_connection,
    save_github_credentials,
    test_and_save_github_connection,
    toggle_github_connection
)

__all__ = [
    'GitHubLLMWrapper',
    'GitHubClientManagerAsync',
    'agent_tool',
    'github_prompts',
    'get_github_tools',
    'ReactGraphState',
    'Context',
    'create_github_graph_with_history',
    'create_github_graph_simple',
    'test_github_connection',
    'save_github_credentials',
    'test_and_save_github_connection',
    'toggle_github_connection'
]

__version__ = '1.0.0'
