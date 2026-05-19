# ConfigurableAI

A common package for switching between different AI providers like OpenAI, GCP, Azure, etc. This package provides a unified interface that allows frontend users to easily switch between AI providers without changing their code.

## Features

- **Unified Interface**: Single API for multiple AI providers
- **Easy Provider Switching**: Change providers with a simple configuration
- **Environment Variable Support**: Configure providers using environment variables
- **File-based Configuration**: Support for JSON configuration files
- **Extensible**: Easy to add new AI providers
- **Async Support**: Full async/await support for all operations

## Supported Providers

- **OpenAI**: GPT models and embeddings
- **Google Cloud Platform (GCP)**: Vertex AI models
- **Azure OpenAI**: Azure-hosted OpenAI models
- **Extensible**: Easy to add custom providers

## Installation

```bash
pip install configurable-ai
```

## Quick Start

### Basic Usage

```python
from common_adapters.configurableAI import ConfigurableAIManager

# Create manager
manager = ConfigurableAIManager()

# Configure OpenAI provider
manager.configure_from_env("openai")

# Generate text
response = await manager.generate_text("Hello, how are you?")
print(response)

# Generate embeddings
embeddings = await manager.generate_embeddings(["Hello", "World"])
print(embeddings)
```

### Using Different Providers

```python
# Configure multiple providers
manager.configure_from_env("openai")
manager.configure_from_env("azure")
manager.configure_from_env("gcp")

# Switch between providers
await manager.generate_text("Hello", provider="openai")
await manager.generate_text("Hello", provider="azure")
await manager.generate_text("Hello", provider="gcp")

# Set default provider
manager.set_current_provider("azure")
await manager.generate_text("Hello")  # Uses Azure
```

### Configuration from Dictionary

```python
# Configure with dictionary
openai_config = {
    "api_key": "your-api-key",
    "model": "gpt-4",
    "organization": "your-org"
}

manager.configure_provider("openai", openai_config)
```

### Configuration from File

```json
{
  "default_provider": "openai",
  "providers": {
    "openai": {
      "api_key": "your-openai-key",
      "model": "gpt-4",
      "organization": "your-org"
    },
    "azure": {
      "api_key": "your-azure-key",
      "endpoint": "https://your-resource.openai.azure.com/",
      "deployment_name": "gpt-4",
      "api_version": "2023-12-01-preview"
    }
  }
}
```

```python
manager.configure_from_file("ai_config.json")
```

## Environment Variables

### OpenAI
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_ORGANIZATION`: Your OpenAI organization (optional)
- `OPENAI_MODEL`: Default model to use (optional)

### Azure OpenAI
- `AZURE_API_KEY`: Your Azure OpenAI API key
- `AZURE_ENDPOINT`: Your Azure OpenAI endpoint
- `AZURE_DEPLOYMENT_NAME`: Your deployment name
- `AZURE_API_VERSION`: API version (optional, defaults to 2023-12-01-preview)

### GCP
- `GCP_PROJECT_ID`: Your GCP project ID
- `GCP_LOCATION`: GCP location (optional, defaults to us-central1)
- `GCP_MODEL`: Default model to use (optional)

### General
- `DEFAULT_AI_PROVIDER`: Default provider to use (optional, defaults to openai)

## Advanced Usage

### Custom Provider

```python
from common_adapters.configurableAI.providers import BaseAIProvider, ProviderRegistry
from common_adapters.configurableAI.config import AIProviderConfig

class CustomProvider(BaseAIProvider):
    async def generate_text(self, prompt: str, **kwargs) -> str:
        # Your implementation
        pass
    
    async def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        # Your implementation
        pass
    
    def validate_config(self) -> bool:
        # Your validation logic
        return True

# Register the provider
ProviderRegistry.register_provider("custom", CustomProvider)

# Use it
manager = ConfigurableAIManager()
manager.configure_provider("custom", AIProviderConfig(
    provider_name="custom",
    api_key="your-key"
))
```

### Convenience Function

```python
from common_adapters.configurableAI import get_ai_manager

# Quick setup with auto-configuration
manager = get_ai_manager("openai", auto_configure=True)
response = await manager.generate_text("Hello!")
```

## API Reference

### ConfigurableAIManager

#### Methods

- `configure_provider(provider_name, config)`: Configure a provider
- `configure_from_env(provider_name)`: Configure from environment variables
- `configure_from_file(config_file)`: Configure from JSON file
- `set_current_provider(provider_name)`: Set active provider
- `get_current_provider()`: Get current provider name
- `list_configured_providers()`: List configured providers
- `list_available_providers()`: List all available provider types
- `generate_text(prompt, provider=None, **kwargs)`: Generate text
- `generate_embeddings(texts, provider=None, **kwargs)`: Generate embeddings

### Provider Registry

- `ProviderRegistry.register_provider(name, provider_class)`: Register custom provider
- `ProviderRegistry.get_provider(name)`: Get provider class
- `ProviderRegistry.list_providers()`: List available providers
- `ProviderRegistry.is_provider_available(name)`: Check if provider is available

## Error Handling

```python
try:
    manager = ConfigurableAIManager()
    manager.configure_from_env("openai")
    response = await manager.generate_text("Hello")
except ValueError as e:
    print(f"Configuration error: {e}")
except ImportError as e:
    print(f"Missing dependency: {e}")
```

## License

MIT License