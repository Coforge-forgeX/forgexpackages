"""
TrustAI Integration Package

This package provides integration with TrustAI API for secure LLM operations with guardrails.
It includes database management, workspace registration, and LangChain-compatible chat models.

Main Components:
- TrustAIDatabaseManager: Handles database initialization and ORM
- TrustAIWorkspaceIntegration: Manages workspace registration and configuration
- TrustAIProvider: Provider implementation for LLM calls
- TrustAIChatModel: LangChain-compatible chat model wrapper
- LLMHelper: Convenience methods for LLM operations

Quick Start:
    ```python
    from common_adapters.trustai import (
        get_trustai_workspace_integration,
        get_trustai_llm,
        get_llm_helper
    )

    # Initialize workspace integration
    integration = get_trustai_workspace_integration(db_url)

    # Register workspace
    app_id, api_key = await integration.register_workspace(
        workspace_id, trustai_config
    )

    # Get LLM for agent
    llm = get_trustai_llm(workspace_id, agent_id)
    response = await llm.generate_text("Your prompt here")

    # Use LLM helper
    helper = get_llm_helper(db_url)
    response = helper.get_llm_response(workspace_id, agent_id, "Your prompt")
    ```
"""

from .database import TrustAIDatabaseManager
from .workspace_integration import TrustAIWorkspaceIntegration
from .provider import TrustAIProvider
from .langchain_adapter import TrustAIChatModel
from .llm_helper import TrustAILLMHelper, get_llm_helper
from .endpoints import TrustAIEndpoints

__version__ = "1.0.0"

__all__ = [
    "TrustAIDatabaseManager",
    "TrustAIWorkspaceIntegration",
    "TrustAIProvider",
    "TrustAIChatModel",
    "TrustAILLMHelper",
    "get_llm_helper",
    "TrustAIEndpoints",
]
