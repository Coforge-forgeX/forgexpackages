"""
Configuration classes for AI providers.
Only supports Azure and Quasar providers.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import os


@dataclass
class AIProviderConfig:
    """Base configuration for AI providers."""
    provider_name: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    model: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None

    @classmethod
    def from_env(cls, provider_name: str) -> "AIProviderConfig":
        """Create configuration from environment variables."""
        prefix = f"{provider_name.upper()}_"
        
        return cls(
            provider_name=provider_name,
            api_key=os.getenv(f"{prefix}API_KEY"),
            endpoint=os.getenv(f"{prefix}ENDPOINT"),
            model=os.getenv(f"{prefix}MODEL"),
            extra_params={}
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIProviderConfig":
        """Create configuration from dictionary."""
        return cls(
            provider_name=data.get("provider_name"),
            api_key=data.get("api_key"),
            endpoint=data.get("endpoint"),
            model=data.get("model"),
            extra_params=data.get("extra_params", {})
        )


@dataclass
class AzureOpenAIConfig(AIProviderConfig):
    """Azure OpenAI configuration."""
    deployment_name: Optional[str] = None
    api_version: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "AzureOpenAIConfig":
        """Create Azure OpenAI configuration from environment variables."""
        import logging
        logger = logging.getLogger(__name__)
        
        api_key = os.getenv("AZURE_OPENAI_LLM_MODEL_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_LLM_MODEL_API_BASE")
        model = os.getenv("AZURE_OPENAI_LLM_MODEL_LLM_MODEL")
        api_version = os.getenv("AZURE_OPENAI_LLM_MODEL_API_VERSION", "2024-12-01-preview")
        
        logger.info(f"Azure config from env - API Key: {'***' if api_key else 'None'}, Endpoint: {endpoint}, Model: {model}, Version: {api_version}")
        
        return cls(
            provider_name="azure",
            api_key=api_key,
            endpoint=endpoint,
            model=model,
            deployment_name=model,
            api_version=api_version,
            extra_params={}
        )


@dataclass
class QuasarConfig(AIProviderConfig):
    """Quasar API configuration."""
    
    @classmethod
    def from_env(cls) -> "QuasarConfig":
        """Create Quasar configuration from environment variables."""
        import logging
        logger = logging.getLogger(__name__)
        
        api_key = os.getenv("QUASAR_API_KEY")
        endpoint = os.getenv("QUASAR_ENDPOINT_URL")
        model = os.getenv("QUASAR_MODEL", "claude-sonnet-4")
        
        logger.info(f"Quasar config from env - API Key: {'***' if api_key else 'None'}, Endpoint: {endpoint}, Model: {model}")
        
        return cls(
            provider_name="quasar",
            api_key=api_key,
            endpoint=endpoint,
            model=model,
            extra_params={}
        )