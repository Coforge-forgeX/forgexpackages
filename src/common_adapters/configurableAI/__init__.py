"""
ConfigurableAI - A unified interface for multiple AI providers.

This package provides a simple way to switch between different AI providers
(OpenAI, Azure OpenAI, GCP Vertex AI, etc.) with minimal code changes.

Includes the LLM Router Config Store for MongoDB-backed workspace/agent
LLM configuration, so any agent can use the configured LLM without
depending on kbcurator.
"""

from .manager import ConfigurableAIManager, get_ai_manager, clear_ai_manager_cache, get_cached_manager_count
from .config import (
    AIProviderConfig,
    AzureOpenAIConfig,
    QuasarConfig
)
from .providers import BaseAIProvider, ProviderRegistry
from .llm_router_config_store import (
    LLMRouterConfigStore,
    llm_router_config_store,
    SUPPORTED_PROVIDERS,
)
from .llm_router import get_configured_llm_manager, invalidate_llm_cache

__version__ = "0.1.0"

__all__ = [
    "ConfigurableAIManager",
    "get_ai_manager",
    "clear_ai_manager_cache",
    "get_cached_manager_count",
    "AIProviderConfig",
    "AzureOpenAIConfig",
    "QuasarConfig",
    "BaseAIProvider",
    "ProviderRegistry",
    # LLM Router
    "LLMRouterConfigStore",
    "llm_router_config_store",
    "SUPPORTED_PROVIDERS",
    "get_configured_llm_manager",
    "invalidate_llm_cache",
]