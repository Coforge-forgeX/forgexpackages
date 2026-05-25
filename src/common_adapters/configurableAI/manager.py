"""
ConfigurableAI Manager - Main interface for AI provider switching.
"""

from typing import Dict, Any, Optional, List, Union
import logging
import os
import json
from .providers import ProviderRegistry, BaseAIProvider
from .config import (
    AIProviderConfig, 
    OpenAIConfig, 
    GCPConfig, 
    AzureOpenAIConfig,
    QuasarConfig
)

logger = logging.getLogger(__name__)


class ConfigurableAIManager:
    """
    Main manager class for configurable AI providers.
    
    This class provides a simple interface to switch between different AI providers
    and perform common AI operations like text generation and embeddings.
    """
    
    def __init__(self, default_provider: Optional[str] = None):
        """
        Initialize the ConfigurableAI Manager.
        
        Args:
            default_provider: Default provider to use if none specified
        """
        self._providers: Dict[str, BaseAIProvider] = {}
        self._current_provider: Optional[str] = None
        self._default_provider = default_provider or os.getenv("DEFAULT_AI_PROVIDER", "openai")
        
        logger.info(f"Initialized ConfigurableAI Manager with default provider: {self._default_provider}")
    
    def configure_provider(self, provider_name: str, config: Union[AIProviderConfig, Dict[str, Any]]) -> None:
        """
        Configure an AI provider.
        
        Args:
            provider_name: Name of the provider (e.g., 'openai', 'gcp', 'azure')
            config: Provider configuration (AIProviderConfig object or dict)
        """
        provider_name = provider_name.lower()
        
        # Convert dict to appropriate config object if needed
        if isinstance(config, dict):
            config = self._create_config_from_dict(provider_name, config)
        
        # Get provider class and create instance
        provider_class = ProviderRegistry.get_provider(provider_name)
        provider_instance = provider_class(config)
        
        # Validate configuration
        if not provider_instance.validate_config():
            raise ValueError(f"Invalid configuration for provider '{provider_name}'")
        
        self._providers[provider_name] = provider_instance
        
        # Set as current provider if it's the first one or default
        if not self._current_provider or provider_name == self._default_provider:
            self._current_provider = provider_name
        
        logger.info(f"Configured provider '{provider_name}' successfully")
    
    def configure_from_env(self, provider_name: str) -> None:
        """
        Configure a provider using environment variables.
        
        Args:
            provider_name: Name of the provider to configure
        """
        provider_name = provider_name.lower()
        
        # Create config from environment
        if provider_name == "openai":
            config = OpenAIConfig.from_env()
        elif provider_name == "gcp":
            config = GCPConfig.from_env()
        elif provider_name == "azure":
            config = AzureOpenAIConfig.from_env()
        elif provider_name == "quasar":
            config = QuasarConfig.from_env()
        else:
            config = AIProviderConfig.from_env(provider_name)
        
        self.configure_provider(provider_name, config)
    
    def configure_from_file(self, config_file: str) -> None:
        """
        Configure providers from a JSON configuration file.
        
        Args:
            config_file: Path to JSON configuration file
        """
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        providers_config = config_data.get('providers', {})
        default_provider = config_data.get('default_provider', self._default_provider)
        
        for provider_name, provider_config in providers_config.items():
            self.configure_provider(provider_name, provider_config)
        
        if default_provider in self._providers:
            self.set_current_provider(default_provider)
    
    def set_current_provider(self, provider_name: str) -> None:
        """
        Set the current active provider.
        
        Args:
            provider_name: Name of the provider to set as current
        """
        provider_name = provider_name.lower()
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' is not configured. Available: {list(self._providers.keys())}")
        
        self._current_provider = provider_name
        logger.info(f"Set current provider to: {provider_name}")
    
    def get_current_provider(self) -> Optional[str]:
        """Get the name of the current active provider."""
        return self._current_provider
    
    def list_configured_providers(self) -> List[str]:
        """List all configured providers."""
        return list(self._providers.keys())
    
    def list_available_providers(self) -> List[str]:
        """List all available provider types."""
        return ProviderRegistry.list_providers()
    
    async def generate_text(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Generate text using the specified or current provider.
        
        Args:
            prompt: Text prompt for generation
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            Generated text
        """
        provider_name = provider or self._current_provider
        
        if not provider_name:
            raise ValueError("No provider specified and no current provider set")
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' is not configured")
        
        logger.info(f"Generating text using provider: {provider_name}")
        return await self._providers[provider_name].generate_text(prompt, **kwargs)
    
    async def generate_embeddings(self, texts: List[str], provider: Optional[str] = None, **kwargs) -> List[List[float]]:
        """
        Generate embeddings using the specified or current provider.
        
        Args:
            texts: List of texts to generate embeddings for
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            List of embeddings
        """
        provider_name = provider or self._current_provider
        
        if not provider_name:
            raise ValueError("No provider specified and no current provider set")
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' is not configured")
        
        logger.info(f"Generating embeddings using provider: {provider_name}")
        return await self._providers[provider_name].generate_embeddings(texts, **kwargs)
    
    def _create_config_from_dict(self, provider_name: str, config_dict: Dict[str, Any]) -> AIProviderConfig:
        """Create appropriate config object from dictionary."""
        config_dict['provider_name'] = provider_name
        
        if provider_name == "openai":
            return OpenAIConfig(**config_dict)
        elif provider_name == "gcp":
            return GCPConfig(**config_dict)
        elif provider_name == "azure":
            return AzureOpenAIConfig(**config_dict)
        elif provider_name == "quasar":
            return QuasarConfig(**config_dict)
        else:
            return AIProviderConfig.from_dict(config_dict)


# Convenience function for quick setup
def get_ai_manager(provider_name: str, auto_configure: bool = True) -> ConfigurableAIManager:
    """
    Get a ConfigurableAI Manager with a specific provider.
    
    Args:
        provider_name: Name of the provider to configure
        auto_configure: Whether to auto-configure from environment variables
        
    Returns:
        Configured ConfigurableAIManager instance
    """
    manager = ConfigurableAIManager(default_provider=provider_name)
    
    if auto_configure:
        manager.configure_from_env(provider_name)
    
    return manager