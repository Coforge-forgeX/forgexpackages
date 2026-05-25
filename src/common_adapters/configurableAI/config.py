"""
Configuration classes for AI providers.
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
class OpenAIConfig(AIProviderConfig):
    """OpenAI specific configuration."""
    organization: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        """Create OpenAI configuration from environment variables."""
        base_config = super().from_env("openai")
        return cls(
            provider_name="openai",
            api_key=base_config.api_key,
            endpoint=base_config.endpoint,
            model=base_config.model or "gpt-3.5-turbo",
            organization=os.getenv("OPENAI_ORGANIZATION"),
            extra_params=base_config.extra_params
        )


@dataclass 
class GCPConfig(AIProviderConfig):
    """Google Cloud Platform AI configuration."""
    project_id: Optional[str] = None
    location: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "GCPConfig":
        """Create GCP configuration from environment variables."""
        base_config = super().from_env("gcp")
        return cls(
            provider_name="gcp",
            api_key=base_config.api_key,
            endpoint=base_config.endpoint,
            model=base_config.model or "text-bison",
            project_id=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION", "us-central1"),
            extra_params=base_config.extra_params
        )


@dataclass
class AzureOpenAIConfig(AIProviderConfig):
    """Azure OpenAI configuration."""
    deployment_name: Optional[str] = None
    api_version: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "AzureOpenAIConfig":
        """Create Azure OpenAI configuration from environment variables."""
        return cls(
            provider_name="azure",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-12-01-preview"),
            extra_params={}
        )


@dataclass
class QuasarConfig(AIProviderConfig):
    """Quasar API configuration."""
    
    @classmethod
    def from_env(cls) -> "QuasarConfig":
        """Create Quasar configuration from environment variables."""
        return cls(
            provider_name="quasar",
            api_key=os.getenv("QUASAR_API_KEY"),
            endpoint=os.getenv("QUASAR_ENDPOINT_URL"),
            model=os.getenv("QUASAR_MODEL", "claude-sonnet-4"),
            extra_params={}
        )