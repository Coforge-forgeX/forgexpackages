"""
ConfigurableAI Manager - Main interface for AI provider switching.
"""

from typing import Dict, Any, Optional, List, Union
import logging
import os
import json
import asyncio
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
    
    def configure_from_env(self, provider_name: str) -> bool:
        """
        Configure a provider using environment variables.
        
        Args:
            provider_name: Name of the provider to configure
            
        Returns:
            bool: True if configuration was successful, False otherwise
        """
        provider_name = provider_name.lower()
        
        try:
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
            
            logger.info(f"Created {provider_name} config: api_key={'***' if config.api_key else 'None'}, endpoint={config.endpoint}, model={config.model}")
            
            # Validate that required fields are present
            if not config.api_key:
                logger.error(f"Missing API key for {provider_name} provider")
                return False
            
            if not config.endpoint:
                logger.error(f"Missing endpoint for {provider_name} provider")
                return False
                
            if not config.model:
                logger.error(f"Missing model for {provider_name} provider")
                return False
            
            logger.info(f"All required fields present for {provider_name}, proceeding with configuration")
            self.configure_provider(provider_name, config)
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure provider {provider_name} from environment: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
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
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """
        Get the current configuration status.
        
        Returns:
            Dictionary containing configuration status information
        """
        return {
            "current_provider": self._current_provider,
            "configured_providers": list(self._providers.keys()),
            "available_providers": self.list_available_providers(),
            "default_provider": self._default_provider,
            "total_configured": len(self._providers),
            "is_configured": len(self._providers) > 0,
            "has_current_provider": self._current_provider is not None
        }
    
    def generate_text(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Generate text using the specified or current provider (synchronous).
        
        Args:
            prompt: Text prompt for generation
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            Generated text
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_running_loop()
            # If we're in an event loop, we need to use a different approach
            import concurrent.futures
            import threading
            
            def run_in_thread():
                # Create a new event loop in a separate thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self.generate_text_async(prompt, provider, **kwargs)
                    )
                finally:
                    new_loop.close()
            
            # Run in a separate thread to avoid event loop conflict
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
                
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.generate_text_async(prompt, provider, **kwargs))
    
    async def generate_text_async(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Generate text using the specified or current provider (asynchronous).
        
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
    
    def generate_embeddings(self, texts: List[str], provider: Optional[str] = None, **kwargs) -> List[List[float]]:
        """
        Generate embeddings using the specified or current provider (synchronous).
        
        Args:
            texts: List of texts to generate embeddings for
            provider: Specific provider to use (optional, uses current if not specified)
            **kwargs: Additional parameters for the provider
            
        Returns:
            List of embeddings
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_running_loop()
            # If we're in an event loop, we need to use a different approach
            import concurrent.futures
            import threading
            
            def run_in_thread():
                # Create a new event loop in a separate thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self.generate_embeddings_async(texts, provider, **kwargs)
                    )
                finally:
                    new_loop.close()
            
            # Run in a separate thread to avoid event loop conflict
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
                
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.generate_embeddings_async(texts, provider, **kwargs))
    
    async def generate_embeddings_async(self, texts: List[str], provider: Optional[str] = None, **kwargs) -> List[List[float]]:
        """
        Generate embeddings using the specified or current provider (asynchronous).
        
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


# Convenience function for quick setup with optional persistence
def get_ai_manager(
    provider_name: str = "azure", 
    auto_configure: bool = True, 
    workspace_id: Optional[int] = None, 
    agent_id: Optional[int] = None
) -> ConfigurableAIManager:
    """
    Get a ConfigurableAI Manager with optional database persistence.
    
    Args:
        provider_name: Name of the provider to configure (used only for simple mode)
        auto_configure: Whether to auto-configure from environment variables (used only for simple mode)
        workspace_id: ID of the workspace (enables database persistence if provided)
        agent_id: ID of the agent (None for workspace-level config)
        
    Returns:
        Configured ConfigurableAIManager instance
        
    Examples:
        # Simple mode (no persistence)
        manager = get_ai_manager("azure", auto_configure=True)
        
        # Persistent mode (with database)
        manager = get_ai_manager(workspace_id=1, agent_id=42)
        manager = get_ai_manager(workspace_id=1)  # workspace default
    """
    # If workspace_id is provided, use persistent mode
    if workspace_id is not None:
        return _get_persistent_manager(workspace_id, agent_id)
    
    # Otherwise, use simple mode
    manager = ConfigurableAIManager(default_provider=provider_name)
    
    if auto_configure:
        manager.configure_from_env(provider_name)
    
    return manager


# Cache for AI manager instances per workspace/agent
_ai_managers: Dict[str, ConfigurableAIManager] = {}


def _get_manager_key(workspace_id: int, agent_id: Optional[int] = None) -> str:
    """Generate a cache key for AI manager instances."""
    return f"ws_{workspace_id}_agent_{agent_id}"


def _get_persistent_manager(workspace_id: int, agent_id: Optional[int] = None) -> ConfigurableAIManager:
    """
    Internal function to get or create an AI manager instance with database persistence.
    
    Args:
        workspace_id: ID of the workspace
        agent_id: ID of the agent (None for workspace-level config)
        
    Returns:
        ConfigurableAIManager instance with database persistence
    """
    key = _get_manager_key(workspace_id, agent_id)
    
    if key not in _ai_managers:
        _ai_managers[key] = ConfigurableAIManager()
        
        # Load configuration from database
        _load_configuration_from_db(_ai_managers[key], workspace_id, agent_id)
        
        logger.info(f"Created new persistent AI manager for workspace {workspace_id}, agent {agent_id}")
    
    return _ai_managers[key]


def _load_configuration_from_db(manager: ConfigurableAIManager, workspace_id: int, agent_id: Optional[int] = None):
    """Load configuration from database and apply to manager."""
    try:
        # Import here to avoid circular dependencies
        from kbcurator.services.agent_llm_configuration_service import agent_llm_config_service
        
        # Get effective configuration (agent-specific or workspace default)
        config = agent_llm_config_service.get_effective_configuration(workspace_id, agent_id)
        
        if config:
            # Configure providers from environment variables
            configured_providers = config['configured_providers'] or []
            
            for provider in configured_providers:
                try:
                    success = manager.configure_from_env(provider)
                    if success:
                        logger.info(f"Configured provider {provider} from environment")
                    else:
                        logger.warning(f"Failed to configure provider {provider} from environment")
                except Exception as e:
                    logger.error(f"Error configuring provider {provider}: {e}")
            
            # Set current provider if specified
            if config['current_provider'] and config['current_provider'] in configured_providers:
                try:
                    manager.set_current_provider(config['current_provider'])
                    logger.info(f"Set current provider to {config['current_provider']}")
                except Exception as e:
                    logger.error(f"Error setting current provider: {e}")
                    
    except ImportError:
        logger.warning("Could not import agent_llm_config_service. Using in-memory mode only.")
    except Exception as e:
        logger.error(f"Failed to load configuration from database: {e}")


def _save_configuration_to_db(workspace_id: int, agent_id: Optional[int], provider: str, set_as_current: bool = False, user_id: Optional[int] = None):
    """Save provider configuration to database."""
    try:
        # Import here to avoid circular dependencies
        from kbcurator.services.agent_llm_configuration_service import agent_llm_config_service
        
        if set_as_current:
            agent_llm_config_service.switch_provider(
                workspace_id=workspace_id,
                provider=provider,
                agent_id=agent_id,
                user_id=user_id
            )
        else:
            agent_llm_config_service.add_provider(
                workspace_id=workspace_id,
                provider=provider,
                agent_id=agent_id,
                set_as_current=False,
                user_id=user_id
            )
        logger.info(f"Saved provider {provider} configuration to database")
    except ImportError:
        logger.warning("Could not import agent_llm_config_service. Configuration not persisted.")
    except Exception as e:
        logger.error(f"Failed to save configuration to database: {e}")


def clear_ai_manager_cache(workspace_id: Optional[int] = None, agent_id: Optional[int] = None):
    """
    Clear AI manager cache for specific workspace/agent or all cached managers.
    
    Args:
        workspace_id: ID of the workspace (None to clear all)
        agent_id: ID of the agent (None to clear workspace default)
    """
    global _ai_managers
    
    if workspace_id is not None:
        key = _get_manager_key(workspace_id, agent_id)
        if key in _ai_managers:
            del _ai_managers[key]
            logger.info(f"Cleared AI manager cache for workspace {workspace_id}, agent {agent_id}")
    else:
        _ai_managers.clear()
        logger.info("Cleared all AI manager cache")


def get_cached_manager_count() -> int:
    """Get the number of cached AI manager instances."""
    return len(_ai_managers)