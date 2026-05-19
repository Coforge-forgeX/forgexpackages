"""
ConfigurableAI - A common package for switching between AI providers.

This package provides a unified interface to switch between different AI providers
like OpenAI, GCP, Azure, AWS, etc. based on configuration.
"""

from .manager import ConfigurableAIManager
from .providers import ProviderRegistry
from .config import AIProviderConfig

__all__ = [
    "ConfigurableAIManager",
    "ProviderRegistry", 
    "AIProviderConfig"
]