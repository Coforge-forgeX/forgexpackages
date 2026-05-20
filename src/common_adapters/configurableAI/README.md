# Common Adapters

A comprehensive collection of reusable adapters for AI services, storage solutions, and integrations.

## Table of Contents
- [Installation](#installation)
- [ConfigurableAI Adapter](#configurableai-adapter)
  - [Quick Start](#quick-start)
  - [Environment Setup](#environment-setup)
  - [Supported Providers](#supported-providers)
  - [Usage Examples](#usage-examples)
  - [Advanced Configuration](#advanced-configuration)
- [Other Adapters](#other-adapters)

## Installation

Install the package directly from the GitHub repository:

```bash
pip install git+https://github.com/Coforge-forgeX/forgexpackages.git@main
```

## ConfigurableAI Adapter

The ConfigurableAI adapter provides a unified interface to switch between different AI providers (OpenAI, Azure OpenAI, Google Cloud, etc.) without changing your code.

### Quick Start

```python
from common_adapters.configurableAI import ConfigurableAIManager
import asyncio

# Initialize the manager
ai_manager = ConfigurableAIManager()

# Configure Azure OpenAI from environment variables
ai_manager.configure_from_env("azure")

# Generate text
async def main():
    response = await ai_manager.generate_text("Hello, how are you?")
    print(response)

asyncio.run(main())
```

### Environment Setup

#### 1. Environment Variables Location

Create a `.env` file in your project root directory (same level as your main Python script or where you run your application). The ConfigurableAI adapter will automatically load environment variables from this file.

**Project Structure:**
```
your-project/
├── .env                    # Environment variables file
├── main.py                # Your main application
├── requirements.txt
└── src/
    └── your_modules/
```

#### 2. Environment Variables for Different Providers

##### Azure OpenAI
```bash
# .env file
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

##### OpenAI
```bash
# .env file
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1  # Optional, defaults to OpenAI API
OPENAI_ORGANIZATION=your_org_id            # Optional
```

##### Google Cloud Platform
```bash
# .env file
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1                   # Optional, defaults to us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

### Supported Providers

| Provider | Status | Models Supported |
|----------|--------|------------------|
| Azure OpenAI | ✅ Ready | GPT-4, GPT-3.5-turbo, Embeddings |
| OpenAI | ✅ Ready | GPT-4, GPT-3.5-turbo, Embeddings |
| Google Cloud | 🚧 Basic | Vertex AI (placeholder implementation) |

### Usage Examples

#### Example 1: Basic Text Generation

```python
from common_adapters.configurableAI import ConfigurableAIManager
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def basic_example():
    # Initialize manager
    manager = ConfigurableAIManager()
    
    # Configure Azure OpenAI from environment
    manager.configure_from_env("azure")
    
    # Generate text
    response = await manager.generate_text("Explain quantum computing in simple terms")
    print(f"AI Response: {response}")

asyncio.run(basic_example())
```

#### Example 2: Switching Between Providers

```python
from common_adapters.configurableAI import ConfigurableAIManager
from common_adapters.configurableAI.config import AzureOpenAIConfig, OpenAIConfig
import asyncio
import os

async def multi_provider_example():
    manager = ConfigurableAIManager()
    
    # Configure multiple providers
    manager.configure_from_env("azure")
    manager.configure_from_env("openai")
    
    # Use Azure OpenAI
    azure_response = await manager.generate_text(
        "What is machine learning?", 
        provider="azure"
    )
    print(f"Azure Response: {azure_response}")
    
    # Switch to OpenAI
    openai_response = await manager.generate_text(
        "What is machine learning?", 
        provider="openai"
    )
    print(f"OpenAI Response: {openai_response}")

asyncio.run(multi_provider_example())
```

#### Example 3: Manual Configuration

```python
from common_adapters.configurableAI import ConfigurableAIManager
from common_adapters.configurableAI.config import AzureOpenAIConfig
import asyncio

async def manual_config_example():
    manager = ConfigurableAIManager()
    
    # Manual configuration (not recommended for production)
    azure_config = AzureOpenAIConfig(
        provider_name="azure",
        api_key="your-api-key",
        endpoint="https://your-resource.openai.azure.com/",
        deployment_name="gpt-4",
        api_version="2024-12-01-preview",
        model="gpt-4"
    )
    
    manager.configure_provider("azure", azure_config)
    
    response = await manager.generate_text("Hello from manually configured Azure!")
    print(response)

asyncio.run(manual_config_example())
```

#### Example 4: Embeddings Generation

```python
from common_adapters.configurableAI import ConfigurableAIManager
import asyncio

async def embeddings_example():
    manager = ConfigurableAIManager()
    manager.configure_from_env("azure")
    
    texts = [
        "Machine learning is a subset of AI",
        "Deep learning uses neural networks",
        "Natural language processing handles text"
    ]
    
    embeddings = await manager.generate_embeddings(
        texts, 
        embedding_deployment="text-embedding-ada-002"
    )
    
    print(f"Generated {len(embeddings)} embeddings")
    print(f"Each embedding has {len(embeddings[0])} dimensions")

asyncio.run(embeddings_example())
```

#### Example 5: Error Handling and Provider Management

```python
from common_adapters.configurableAI import ConfigurableAIManager
import asyncio

async def robust_example():
    manager = ConfigurableAIManager()
    
    try:
        # Configure provider
        manager.configure_from_env("azure")
        
        # Check available providers
        print("Configured providers:", manager.list_configured_providers())
        print("Current provider:", manager.get_current_provider())
        
        # Generate text with error handling
        response = await manager.generate_text(
            "Explain the benefits of renewable energy",
            max_tokens=150,
            temperature=0.7
        )
        print(f"Response: {response}")
        
    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Generation error: {e}")

asyncio.run(robust_example())
```

### Advanced Configuration

#### Configuration from JSON File

```python
# config.json
{
    "default_provider": "azure",
    "providers": {
        "azure": {
            "provider_name": "azure",
            "api_key": "${AZURE_OPENAI_API_KEY}",
            "endpoint": "${AZURE_OPENAI_ENDPOINT}",
            "deployment_name": "${AZURE_OPENAI_CHAT_DEPLOYMENT}",
            "api_version": "${AZURE_OPENAI_API_VERSION}",
            "model": "${AZURE_OPENAI_CHAT_DEPLOYMENT}"
        },
        "openai": {
            "provider_name": "openai",
            "api_key": "${OPENAI_API_KEY}",
            "model": "gpt-4"
        }
    }
}
```

```python
from common_adapters.configurableAI import ConfigurableAIManager
import asyncio

async def json_config_example():
    manager = ConfigurableAIManager()
    
    # Load configuration from JSON file
    manager.configure_from_file("config.json")
    
    response = await manager.generate_text("Hello from JSON config!")
    print(response)

asyncio.run(json_config_example())
```

#### Using in Web Applications (FastAPI Example)

```python
from fastapi import FastAPI, HTTPException
from common_adapters.configurableAI import ConfigurableAIManager
from pydantic import BaseModel
import asyncio

app = FastAPI()

# Initialize AI manager at startup
ai_manager = ConfigurableAIManager()
ai_manager.configure_from_env("azure")

class ChatRequest(BaseModel):
    message: str
    provider: str = "azure"
    max_tokens: int = 150

class ChatResponse(BaseModel):
    response: str
    provider_used: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        response = await ai_manager.generate_text(
            request.message,
            provider=request.provider,
            max_tokens=request.max_tokens
        )
        
        return ChatResponse(
            response=response,
            provider_used=request.provider
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/providers")
async def list_providers():
    return {
        "configured": ai_manager.list_configured_providers(),
        "available": ai_manager.list_available_providers(),
        "current": ai_manager.get_current_provider()
    }
```

### Best Practices

1. **Environment Variables**: Always use environment variables for API keys and sensitive information
2. **Error Handling**: Implement proper error handling for network issues and API failures
3. **Provider Fallback**: Configure multiple providers for redundancy
4. **Rate Limiting**: Implement rate limiting when making many requests
5. **Logging**: Use proper logging to track API usage and errors

### Troubleshooting

#### Common Issues

1. **Import Error**: `No module named 'common_adapters.configurableAI'`
   - **Solution**: Ensure the package is installed correctly: `pip install git+https://github.com/Coforge-forgeX/forgexpackages.git@main`

2. **Environment Variables Not Found**
   - **Solution**: Check that your `.env` file is in the correct location and contains the required variables

3. **Async/Await Errors**
   - **Solution**: Ensure you're using `await` with all async methods and running in an async context

4. **Provider Configuration Errors**
   - **Solution**: Verify your API keys and endpoints are correct

#### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Your ConfigurableAI code here
```

## Other Adapters

The common-adapters package also includes:

- **Storage Adapters**: Azure Blob Storage, AWS S3, MongoDB
- **Langfuse Instrumentation**: LLM observability and monitoring
- **ADO Tool Integration**: Azure DevOps integration tools

For detailed documentation on other adapters, see their respective README files in the package.