# TrustAI Integration Package

Complete integration package for TrustAI API with PostgreSQL database persistence and LangChain compatibility.

## Features

- ✅ **Database Management**: Auto-creates tables, ORM with SQLAlchemy
- ✅ **Workspace Integration**: Register workspaces, manage API keys, configure guardrails
- ✅ **Provider Model Resolution**: User → Workspace-Agent → System default hierarchy
- ✅ **LangChain Compatible**: Drop-in replacement for LangChain chat models
- ✅ **Tool Calling Support**: Full support for LangChain tool binding and structured outputs
- ✅ **LLM Helper**: Convenience methods for common operations

## Installation

The package is part of `common-adapters`. Install with:

```bash
pip install -e forgexpackages/
```

### Required Dependencies

The following dependencies are automatically installed:
- `sqlalchemy` - ORM and database management
- `psycopg2-binary` - PostgreSQL adapter
- `httpx` - HTTP client for API calls
- `langchain-core` - LangChain integration

### Environment Variables

Set these environment variables before using the package:

```bash
# Required for workspace registration and API key generation
export TRUSTAI_MASTER_API_KEY="your-master-api-key"

# Optional: Override TrustAI API endpoint
export TRUSTAI_BASE_URL="https://forgex-dev-trustai-qag.azurewebsites.net"

# Optional: Set API key lifetime (default: 365 days)
export TRUSTAI_API_KEY_LIFETIME_DAYS=365
```

## Database Setup

### Required Existing Tables

The package expects these tables to already exist in your database:
- `workspace_master`
- `agents_details`
- `workspace_agents_mapping_2`
- `users`

### Auto-Created Tables

The package automatically creates these tables if they don't exist:
- `trustai_workspace_config` - TrustAI workspace configuration
- `provider_models` - Available provider-model mappings
- `workspace_agent_provider_model_mapping` - Workspace-agent model configs
- `user_agent_provider_model_preference` - User-specific preferences

## Quick Start

### 1. Initialize Database

```python
from common_adapters.trustai import TrustAIDatabaseManager

# Create database manager
db_manager = TrustAIDatabaseManager(
    database_url="postgresql://user:pass@host:port/dbname"
)

# Initialize tables (auto-creates if they don't exist)
db_manager.initialize_tables()
```

### 2. Register Workspace

```python
import asyncio
from common_adapters.trustai import TrustAIWorkspaceIntegration

# Create workspace integration
integration = TrustAIWorkspaceIntegration(db_manager)

# Register workspace with TrustAI
trustai_config = {
    "application": {
        "name": "My Workspace",
        "description": "Workspace description",
        "line_of_business": "technology",
        "technical_architect": "tech@example.com",
        "business_sponsor": "business@example.com"
    },
    "guardrails": [
        "BSI_DETECTION",
        "TOXIC",
        "PII",
        "PROMPT_INJECTION"
    ],
    "system_config": {
        "guardrail_model": "llama-4-scout",
        "admin_emails": ["admin@example.com"],
        "is_guardrail_notification_enabled": True,
        "input_guardrail_execution_mode": "sync",
        "output_guardrail_execution_mode": "sync"
    }
}

app_id, api_key = await integration.register_workspace(
    workspace_id="ws_123",
    trustai_config=trustai_config
)
print(f"Workspace registered: app_id={app_id}")
```

### 3. Configure Provider Models

```python
# Add a provider model to the system
db_manager.create_provider_model(
    provider_name="azure",
    deployment_name="gpt-4-1",
    trustai_model_key="gpt-4-1",  # TrustAI model key
    is_system_default=True  # Set as system default
)

# Configure workspace-agent default
integration.configure_agent_provider_model(
    workspace_id="ws_123",
    agent_id=1,
    provider_name="azure",
    deployment_name="gpt-4-1",
    created_by=100  # User ID
)

# Set user-specific preference
integration.configure_user_specific_agent_provider_model(
    workspace_id="ws_123",
    user_id=42,
    agent_id=1,
    provider_name="azure",
    deployment_name="gpt-4-1"
)
```

## Usage Examples

### Simple LLM Helper

```python
from common_adapters.trustai import get_llm_helper

# Get helper instance
helper = get_llm_helper(database_url)

# Simple text generation
response = helper.get_llm_response(
    workspace_id="ws_123",
    agent_id=1,
    prompt="What is artificial intelligence?",
    user_id=42,
    user_email="user@example.com"
)
print(response)

# With context and history
response = helper.get_llm_response_with_context(
    workspace_id="ws_123",
    agent_id=1,
    sys_prompt="You are a helpful assistant",
    user_input="Tell me more about AI",
    history=[
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! How can I help?"}
    ],
    user_id=42
)
print(response)
```

### LangChain Integration

```python
from common_adapters.trustai import get_llm_helper
from langgraph.prebuilt import create_react_agent

# Get LangChain-compatible LLM
helper = get_llm_helper(database_url)
llm = helper.get_router_llm(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)

# Use with LangGraph
agent = create_react_agent(llm, tools)
result = agent.invoke({"messages": [("user", "Your message")]})

# Use with LangChain chains
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant"),
    ("user", "{input}")
])
chain = prompt | llm
response = chain.invoke({"input": "Hello!"})
```

### Tool Calling

```python
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Weather in {location}: Sunny, 72°F"

# Bind tools to the model
llm_with_tools = llm.bind_tools([get_weather])

# Invoke with tool calling
response = llm_with_tools.invoke("What's the weather in San Francisco?")
print(response.tool_calls)
```

### Structured Output

```python
from pydantic import BaseModel, Field

class PersonInfo(BaseModel):
    name: str = Field(description="Person's name")
    age: int = Field(description="Person's age")
    occupation: str = Field(description="Person's occupation")

# Get structured output
structured_llm = llm.with_structured_output(PersonInfo)
result = structured_llm.invoke("Tell me about John, a 30 year old engineer")
print(result)  # PersonInfo(name="John", age=30, occupation="engineer")
```

### Direct Provider Usage

```python
from common_adapters.trustai import TrustAIProvider

# Create provider directly
provider = TrustAIProvider(
    db_manager=db_manager,
    workspace_id="ws_123",
    agent_id=1,
    user_id=42,
    user_email="user@example.com"
)

# Generate text
response = await provider.generate_text(
    prompt="Your prompt here",
    temperature=0.7,
    max_tokens=1000
)

# With context
response = await provider.generate_text_with_context(
    system_prompt="You are a helpful assistant",
    user_prompt="Tell me a joke",
    conversation_history=[],
    temperature=0.8
)
```

## Model Resolution Hierarchy

The system resolves provider models using this hierarchy:

1. **User-specific preference** - `user_agent_provider_model_preference` table
2. **Workspace-agent default** - `workspace_agent_provider_model_mapping` table (where `is_default=true`)
3. **System default** - `provider_models` table (where `is_system_default=true`)

This allows for flexible configuration at different levels.

## API Endpoints

All endpoints are configured in `endpoints.py`:

```python
from common_adapters.trustai import TrustAIEndpoints

# Access endpoints
print(TrustAIEndpoints.REGISTER_APP)
print(TrustAIEndpoints.CHAT_COMPLETIONS)

# Override base URL if needed
TrustAIEndpoints.set_base_url("https://custom-trustai-api.com")
```

## Integration with Existing Agents

### Replace ConfigurableAI with TrustAI

**Before (ConfigurableAI):**
```python
from common_adapters.configurableAI import get_configured_llm_manager

manager = get_configured_llm_manager(workspace_id, agent_id)
llm = ConfigurableAIChatModel(manager=manager)
```

**After (TrustAI):**
```python
from common_adapters.trustai import get_llm_helper

helper = get_llm_helper(database_url)
llm = helper.get_router_llm(workspace_id, agent_id, user_id)
```

The interface is fully compatible, so existing LangChain/LangGraph code works without changes!

### Use in ProductOwner Agent

```python
# In your ProductOwner agent code
from common_adapters.trustai import get_router_llm

def get_llm_for_agent(workspace_id, agent_id, database_url):
    """
    Get LangChain-compatible LLM for ProductOwner agent.
    
    Returns TrustAIChatModel which works with LangChain chains,
    LangGraph agents, and tool-calling scenarios.
    """
    return get_router_llm(
        workspace_id=workspace_id,
        agent_id=agent_id,
        database_url=database_url
    )
```

## Logging

The package uses Python's standard logging. Configure it in your application:

```python
import logging

# Set logging level
logging.basicConfig(level=logging.INFO)

# Get TrustAI logger
logger = logging.getLogger("common_adapters.trustai")
logger.setLevel(logging.DEBUG)
```

Log prefixes:
- `[TRUSTAI-PROVIDER]` - Provider operations
- `[TRUSTAI-HELPER]` - Helper operations

## Error Handling

```python
from sqlalchemy.exc import SQLAlchemyError
import httpx

try:
    response = helper.get_llm_response(
        workspace_id="ws_123",
        agent_id=1,
        prompt="Hello"
    )
except SQLAlchemyError as e:
    print(f"Database error: {e}")
except httpx.HTTPError as e:
    print(f"API call error: {e}")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Best Practices

1. **Reuse Database Manager**: Create one `TrustAIDatabaseManager` instance and reuse it
2. **Use LLM Helper**: Use `get_llm_helper()` for convenience methods
3. **Configure Models First**: Add provider models to the database before using
4. **Set System Default**: Always have one model marked as `is_system_default=True`
5. **Use User ID**: Pass `user_id` for user-specific preferences and tracking
6. **Handle Async**: Provider methods are async, use `await` or the helper's sync wrappers

## Troubleshooting

### "No TrustAI configuration found"
- Make sure you've called `integration.register_workspace()` first
- Check if workspace_id exists in `trustai_workspace_config` table

### "No provider model found"
- Add provider models using `db_manager.create_provider_model()`
- Ensure at least one model has `is_system_default=True`

### "TRUSTAI_MASTER_API_KEY is not set"
- Set the environment variable: `export TRUSTAI_MASTER_API_KEY="your-key"`

### Connection errors
- Verify PostgreSQL connection string
- Check network connectivity to TrustAI API
- Ensure TrustAI API endpoint is correct

## Package Structure

```
trustai/
├── __init__.py              # Package exports
├── README.md                # This file
├── endpoints.py             # API endpoint configuration
├── models.py                # SQLAlchemy ORM models
├── database.py              # Database manager
├── workspace_integration.py # Workspace registration and config
├── provider.py              # TrustAI provider implementation
├── langchain_adapter.py     # LangChain compatibility layer
└── llm_helper.py           # Convenience helper methods
```

## Support

For issues or questions:
1. Check the logs with DEBUG level enabled
2. Verify environment variables are set correctly
3. Ensure database tables are created
4. Check TrustAI API connectivity

## Version

Current version: 1.0.0
