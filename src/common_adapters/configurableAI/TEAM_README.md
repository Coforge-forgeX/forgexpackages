# ConfigurableAI - Team Guide

## What is ConfigurableAI?

ConfigurableAI is a **unified interface** that lets you switch between different AI providers (OpenAI, Azure OpenAI, Google Cloud) **without changing your code**. Think of it as a universal remote control for AI services.

## Why Use ConfigurableAI?

### ✅ **Single Code, Multiple Providers**
```python
# Same code works with any provider
manager = ConfigurableAIManager()
response = await manager.generate_text("Hello, how are you?")
```

### ✅ **Easy Provider Switching**
```python
# Switch from OpenAI to Azure without code changes
manager.set_current_provider("azure")  # Now using Azure
manager.set_current_provider("openai") # Now using OpenAI
```

### ✅ **Environment-Based Configuration**
No hardcoded API keys - everything comes from environment variables.

---

## Quick Start (5 Minutes)

### Step 1: Install in Your Project
Add this line to your `pyproject.toml` dependencies:
```toml
"common-adapters @ git+https://github.com/Coforge-forgeX/forgexpackages.git@main"
```

### Step 2: Set Environment Variables
Add these to your `.env` file:
```bash
# For Azure OpenAI (what we currently use)
AZURE_OPENAI_API_KEY=your-azure-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# For OpenAI (optional)
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4

# For Google Cloud (optional)
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
```

### Step 3: Use in Your Code
```python
from common_adapters.configurableAI import ConfigurableAIManager
import asyncio

# Create manager
manager = ConfigurableAIManager()

# Configure Azure (reads from environment)
manager.configure_from_env("azure")

# Generate text
async def chat():
    response = await manager.generate_text("Explain quantum computing in simple terms")
    print(response)

# Run it
asyncio.run(chat())
```

---

## Real Example: Azure OpenAI

Here's exactly how we use it with our current Azure setup:

```python
from common_adapters.configurableAI import ConfigurableAIManager
from common_adapters.configurableAI.config import AzureOpenAIConfig
import asyncio

async def test_azure():
    # Create manager
    manager = ConfigurableAIManager()
    
    # Option 1: Configure from environment (recommended)
    manager.configure_from_env("azure")
    
    # Option 2: Configure manually
    # azure_config = AzureOpenAIConfig(
    #     provider_name="azure",
    #     api_key="your-key",
    #     endpoint="https://your-resource.openai.azure.com/",
    #     deployment_name="your-deployment-name",
    #     api_version="2024-12-01-preview"
    # )
    # manager.configure_provider("azure", azure_config)
    
    # Generate response
    response = await manager.generate_text("Hi, how are you?")
    print(f"AI Response: {response}")

# Run the test
asyncio.run(test_azure())
```

**Expected Output:**
```
AI Response: Hello! I'm just a computer program, but I'm here and ready to help you. How can I assist you today?
```

---

## Environment Variables Reference

### Azure OpenAI (Current Setup)
```bash
AZURE_OPENAI_API_KEY=your-azure-openai-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

### OpenAI (For Future Use)
```bash
OPENAI_API_KEY=sk-your-openai-key
OPENAI_MODEL=gpt-4
OPENAI_ORGANIZATION=your-org-id  # Optional
```

### Google Cloud Platform (For Future Use)
```bash
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GCP_MODEL=text-bison
```

---

## How It Works

### 1. **Manager Pattern**
- `ConfigurableAIManager` is the main class
- It manages multiple AI providers
- Switches between them seamlessly

### 2. **Provider Registry**
- Each AI service has a "provider" (OpenAI, Azure, GCP)
- Providers are registered automatically
- You can add custom providers

### 3. **Configuration Objects**
- Each provider has its own config class
- Configs can be created from environment variables
- Or created manually with dictionaries

### 4. **Unified Interface**
- All providers support the same methods:
  - `generate_text()` - Chat completions
  - `generate_embeddings()` - Vector embeddings

---

## Common Use Cases

### 1. **Chat/Completion**
```python
response = await manager.generate_text(
    "Write a Python function to calculate fibonacci numbers"
)
```

### 2. **Embeddings for RAG**
```python
embeddings = await manager.generate_embeddings([
    "Document chunk 1",
    "Document chunk 2", 
    "Document chunk 3"
])
```

### 3. **Provider Switching**
```python
# Start with Azure
manager.configure_from_env("azure")
response1 = await manager.generate_text("Hello")

# Switch to OpenAI
manager.configure_from_env("openai") 
response2 = await manager.generate_text("Hello")

# Compare responses from different providers
```

### 4. **Multiple Providers**
```python
# Configure multiple providers
manager.configure_from_env("azure")
manager.configure_from_env("openai")

# Use specific provider
azure_response = await manager.generate_text("Hello", provider="azure")
openai_response = await manager.generate_text("Hello", provider="openai")
```

---

## Integration with Existing Code

### In KnowledgeCurator
```python
# Replace direct OpenAI calls
# OLD:
# import openai
# client = openai.OpenAI(api_key="...")
# response = client.chat.completions.create(...)

# NEW:
from common_adapters.configurableAI import ConfigurableAIManager
manager = ConfigurableAIManager()
manager.configure_from_env("azure")
response = await manager.generate_text(prompt)
```

### In LightRAG Integration
```python
# Use for embeddings
embeddings = await manager.generate_embeddings(text_chunks)

# Use for LLM calls
summary = await manager.generate_text(f"Summarize: {document}")
```

---

## Error Handling

```python
try:
    manager = ConfigurableAIManager()
    manager.configure_from_env("azure")
    response = await manager.generate_text("Hello")
except ValueError as e:
    print(f"Configuration error: {e}")
except ImportError as e:
    print(f"Missing dependency: {e}")
except Exception as e:
    print(f"API error: {e}")
```

---

## Testing

### Test Script Location
```
KnowledgeCurator/KnowledgeCurator/test_azure_configurable_ai.py
```

### Run Tests
```bash
cd KnowledgeCurator/KnowledgeCurator
python test_azure_configurable_ai.py
```

### Expected Output
```
[SUCCESS] Azure OpenAI is working correctly!
```

---

## Troubleshooting

### Common Issues

1. **Import Error: No module named 'common_adapters'**
   - Solution: Make sure `common-adapters` is in your `pyproject.toml`

2. **Invalid configuration for provider 'azure'**
   - Solution: Check your environment variables are set correctly

3. **Connection Error**
   - Solution: Verify your API keys and endpoints

4. **Missing boto3**
   - Solution: `pip install boto3`

### Debug Steps
1. Check environment variables: `python -c "import os; print(os.getenv('AZURE_OPENAI_API_KEY'))"`
2. Test import: `python -c "from common_adapters.configurableAI import ConfigurableAIManager"`
3. Run test script: `python test_azure_configurable_ai.py`

---

## Best Practices

### ✅ **Do This**
- Use environment variables for configuration
- Use `configure_from_env()` method
- Handle errors gracefully
- Use async/await properly

### ❌ **Don't Do This**
- Hardcode API keys in code
- Mix different AI client libraries in the same project
- Forget to await async methods

---

## Next Steps

1. **Replace existing AI calls** in your project with ConfigurableAI
2. **Add OpenAI support** by setting `OPENAI_API_KEY`
3. **Add GCP support** by setting GCP environment variables
4. **Create custom providers** for other AI services

---

## Questions?

- Check the main README: `configurableAI/README.md`
- Run the test script: `test_azure_configurable_ai.py`
- Look at usage examples in: `configurableAI/examples.py`

**Remember: One interface, multiple AI providers, zero code changes! 🚀**