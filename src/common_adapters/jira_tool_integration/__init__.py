"""
JIRA Tool Integration Package

This package provides JIRA integration tools for multi-agent systems.
Import the main classes directly from this package across all agents.

Usage:
    from packages.jira_tool_integration import (
        JiraLLMWrapper, 
        JiraClientManagerAsync,
        get_jira_tools
    )
"""

from .jira_client_for_llm import JiraLLMWrapper
from .jira_client_manager import JiraClientManagerAsync
from .jira_prompts import jira_prompts
from .jira_update_config import jira_update_config
from .jira_tools import get_jira_tools
from .jira_graph import (
    ReactGraphState,
    create_jira_graph_with_history
)
from .jira_connection import (
    toggle_jira_connection,
    test_jira_connection
)

__all__ = [
    'JiraLLMWrapper',
    'JiraClientManagerAsync',
    'jira_prompts',
    'jira_update_config',
    'get_jira_tools',
    'ReactGraphState',
    'create_jira_graph_with_history',
    'test_jira_connection',
    'toggle_jira_connection']

__version__ = '1.0.0'
