"""
ConfigurableAI - A unified interface for multiple AI providers.

This package provides a simple way to switch between different AI providers
(OpenAI, Azure OpenAI, GCP Vertex AI, etc.) with minimal code changes.
"""

from .manager import ConfigurableAIManager, get_ai_manager, clear_ai_manager_cache, get_cached_manager_count
from .config import (
    AIProviderConfig,
    OpenAIConfig,
    AzureOpenAIConfig,
    GCPConfig,
    QuasarConfig
)
from .providers import BaseAIProvider, ProviderRegistry

__version__ = "0.1.0"

__all__ = [
    "ConfigurableAIManager",
    "get_ai_manager",
    "clear_ai_manager_cache",
    "get_cached_manager_count",
    "AIProviderConfig",
    "OpenAIConfig", 
    "AzureOpenAIConfig",
    "GCPConfig",
    "QuasarConfig",
    "BaseAIProvider",
    "ProviderRegistry"
]