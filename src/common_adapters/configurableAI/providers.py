"""
Provider registry and base provider interface.
Only supports Azure and Quasar providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Type, Any, List, Optional
import logging
from .config import AIProviderConfig

logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, config: AIProviderConfig):
        self.config = config
        self.provider_name = config.provider_name
    
    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using the AI provider."""
        pass
    
    @abstractmethod
    async def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generate embeddings using the AI provider."""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        pass


class AzureOpenAIProvider(BaseAIProvider):
    """Azure OpenAI provider implementation."""
    
    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self._client = None
        
    def _get_client(self):
        """Lazy initialization of Azure OpenAI client."""
        if self._client is None:
            try:
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    api_key=self.config.api_key,
                    azure_endpoint=self.config.endpoint,
                    api_version=getattr(self.config, 'api_version', '2023-12-01-preview')
                )
            except ImportError:
                raise ImportError("openai package is required for Azure OpenAI provider")
        return self._client
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using Azure OpenAI."""
        import asyncio
        
        def _sync_generate():
            client = self._get_client()
            
            # Azure OpenAI client is synchronous, not async
            response = client.chat.completions.create(
                model=getattr(self.config, 'deployment_name', None) or self.config.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            
            return response.choices[0].message.content
        
        # Run the synchronous call in a thread pool to make it async-compatible
        return await asyncio.get_event_loop().run_in_executor(None, _sync_generate)
    
    async def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI."""
        import asyncio
        
        def _sync_generate_embeddings():
            client = self._get_client()
            
            # Azure OpenAI client is synchronous, not async
            response = client.embeddings.create(
                model=kwargs.get('embedding_deployment', 'text-embedding-ada-002'),
                input=texts
            )
            
            return [data.embedding for data in response.data]
        
        # Run the synchronous call in a thread pool to make it async-compatible
        return await asyncio.get_event_loop().run_in_executor(None, _sync_generate_embeddings)
    
    def validate_config(self) -> bool:
        """Validate Azure OpenAI configuration."""
        return bool(self.config.api_key and self.config.endpoint)


class QuasarProvider(BaseAIProvider):
    """Quasar API provider implementation."""
    
    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self._client = None
        
    def _get_client(self):
        """Lazy initialization of HTTP client for Quasar API."""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(
                    headers={
                        "Content-Type": "application/json",
                        "X-API-KEY": self.config.api_key
                    },
                    timeout=60.0
                )
            except ImportError:
                raise ImportError("httpx package is required for Quasar provider")
        return self._client
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using Quasar API."""
        client = self._get_client()
        
        payload = {
            "model": self.config.model or "claude-sonnet-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 100)
        }
        
        response = await client.post(self.config.endpoint, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data['choices'][0]['message']['content']
    
    async def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generate embeddings using Quasar API."""
        # Quasar might not support embeddings, return placeholder
        logger.warning("Quasar embeddings not implemented")
        return [[0.0] * 768 for _ in texts]  # Placeholder
    
    def validate_config(self) -> bool:
        """Validate Quasar configuration."""
        return bool(self.config.api_key and self.config.endpoint)


class ProviderRegistry:
    """Registry for AI providers. Only supports Azure and Quasar."""
    
    _providers: Dict[str, Type[BaseAIProvider]] = {
        "azure": AzureOpenAIProvider,
        "quasar": QuasarProvider
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseAIProvider]):
        """Register a new AI provider."""
        cls._providers[name.lower()] = provider_class
        logger.info(f"Registered AI provider: {name}")
    
    @classmethod
    def get_provider(cls, name: str) -> Type[BaseAIProvider]:
        """Get a provider class by name."""
        provider_class = cls._providers.get(name.lower())
        if not provider_class:
            available = list(cls._providers.keys())
            raise ValueError(f"Provider '{name}' not found. Available providers: {available}")
        return provider_class
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """List all available providers."""
        return list(cls._providers.keys())
    
    @classmethod
    def is_provider_available(cls, name: str) -> bool:
        """Check if a provider is available."""
        return name.lower() in cls._providers