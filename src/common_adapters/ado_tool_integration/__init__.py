"""
Azure DevOps Tool Integration Package

This package provides Azure DevOps integration tools for multi-agent systems.
Import the main classes directly from this package across all agents.

Usage:
    from packages.ado_tool_integration import (
        AzureDevOpsLLMWrapper, 
        AzureDevOpsClientManagerAsync,
        get_azure_devops_tools
    )
"""

from .azure_devops_client_for_llm import AzureDevOpsLLMWrapper
from .azure_devops_client_manager import AzureDevOpsClientManagerAsync
from .azure_devops_prompts import azure_devops_prompts
from .azure_devops_update_config import azure_devops_update_config
from .azure_devops_tools import get_azure_devops_tools
from .azure_devops_graph import (
    ReactGraphState,
    create_azure_devops_graph_with_history
)
from .azure_devops_connection import (
    test_azure_devops_connection,
    toggle_azure_devops_connection
)

__all__ = [
    'AzureDevOpsLLMWrapper',
    'AzureDevOpsClientManagerAsync',
    'azure_devops_prompts',
    'azure_devops_update_config',
    'get_azure_devops_tools',
    'ReactGraphState',
    'create_azure_devops_graph_with_history',
    'test_azure_devops_connection',
    'toggle_azure_devops_connection']

__version__ = '1.0.0'
