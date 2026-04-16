# Azure DevOps Tool Integration Package

A shared package providing Azure DevOps integration for all Forgex agents with LangGraph-based reactive agent workflow.

## 📦 What's Included

```
packages/ado_tool_integration/
├── __init__.py                          # Package exports
├── requirements.txt                     # ADO dependencies 
├── azure_devops_client_for_llm.py      # 40+ Azure DevOps API methods
├── azure_devops_client_manager.py       # Async client with caching
├── azure_devops_graph.py                # LangGraph agent implementation
├── azure_devops_prompts.py              # System prompts
├── azure_devops_tools.py                # get_azure_devops_tools() helper
├── azure_devops_connection.py           # Connection test/toggle utilities
├── azure_devops_update_config.py        # Config validator
└── README.md                            # This file
```

---

## 🚀 Integration Guide (Step-by-Step)

### Step 1: Update `requirements.txt`

**File:** `agents/your_agent/requirements.txt`
---

### Step 2: Update `server.py` - Initialize ADO Client Manager

**File:** `agents/your_agent/server.py`

**2.1** Add imports at the top:
```python
from ado_tool_integration import AzureDevOpsClientManagerAsync
```

**2.2** Declare global variable (with other globals):
```python
# Global variables
azure_devops_client_manager = None
```

**2.3** Initialize in your lifespan function:
```python
@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Lifespan context manager."""
    print("🚀 Starting Your Agent...")
    
    # Initialize MongoDB and other services
    mongo_client = get_mongodb_client()
    
    global azure_devops_client_manager, user_config_manager
    
    try:
        # Initialize config manager first (required for ADO)
        user_config_manager = UserConfigManager(mongo_client)
        
        # Initialize ADO client manager with config manager
        azure_devops_client_manager = AzureDevOpsClientManagerAsync(
            redis_client=r,  # Optional: for caching
            config_manager=user_config_manager  # Required
        )
        
        print("✅ Azure DevOps client manager initialized")
    except Exception as e:
        print(f"✗ Startup initialization failed: {e}")
    
    try:
        yield
    finally:
        print("🛑 Shutting down...")
        mongo_client.close()
```

---

### Step 3: Create `tools/azure_devops_agent.py` - Main Integration

**File:** `agents/your_agent/tools/azure_devops_agent.py`

Create a complete Azure DevOps agent tool with LangGraph integration:

```python
from main import os
import sys

import server
from server import mcp
import langchain_core
from langchain_openai import AzureChatOpenAI
from ado_tool_integration import (
    AzureDevOpsLLMWrapper as AzureDevOps,
    azure_devops_prompts,
    get_azure_devops_tools,
    ReactGraphState,
    create_azure_devops_graph_with_history,
    test_azure_devops_connection as test_ado_connection,
    toggle_azure_devops_connection as toggle_ado_connection
)
import asyncio
from typing import Any
from langchain_core.messages import SystemMessage
from langchain_core.tools.base import _infer_arg_descriptions
import logging
import traceback

logger = logging.getLogger("azure_devops_agent")

# Get context window size from environment
msgs = int(os.getenv("YOUR_AGENT_CONTEXT_WINDOW_SIZE", 7))

# Initialize LLM for ADO agent
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_LLM_MODEL_API_BASE"),
    api_key=os.getenv("AZURE_OPENAI_LLM_MODEL_API_KEY"),
    azure_deployment=os.getenv("AZURE_OPENAI_LLM_MODEL_LLM_MODEL"),
    api_version=os.getenv("AZURE_OPENAI_LLM_MODEL_API_VERSION")
)

# Lazy initialization for the Azure DevOps graph
_react_azure_devops_agent = None

def get_react_azure_devops_agent():
    """Lazily initialize and return the Azure DevOps graph agent."""
    global _react_azure_devops_agent
    if _react_azure_devops_agent is None:
        _react_azure_devops_agent = create_azure_devops_graph_with_history(
            server.session, 
            msgs
        )
    return _react_azure_devops_agent


@mcp.tool()
async def azure_devops_agent(
    workspace_id: str, 
    user_id: str, 
    conversation_id: str, 
    job_id: str | None = None, 
    agent_feed: list | None = None
) -> dict[str, Any]:
    """
    This tool helps interact with Azure DevOps to create, update, fetch work items, 
    boards, sprints and projects based on user prompts.
    
    Args:
        workspace_id: unique identifier for the workspace.
        user_id: unique identifier for the user.
        conversation_id: unique identifier for the conversation.
        job_id: when the request is a workflow job.
        agent_feed: the agents input feed document names.
    """
    if user_id is None:
        return {"status": "error", "error": "user_id cannot be null"}
    
    try:
        # Get ADO client from the shared manager
        azure_devops_client = await server.azure_devops_client_manager.get_client(
            workspace_id, user_id, conversation_id
        )
    except Exception as e:
        logger.error(f"Error creating Azure DevOps client: {e}")
        return {"status": "error", "message": str(e)}
    
    # Get all ADO tools
    tools = get_azure_devops_tools(azure_devops_client)
    
    # Build tool descriptions for the system prompt
    details_of_tools = []
    for i, tool in enumerate(tools):
        desc, arg_descriptions = _infer_arg_descriptions(tool)
        desc = desc.split(":param")[0].strip()
        tool_description = f"{i+1}. {tool.__name__}: {desc}\n"
        details_of_tools.append(tool_description)
    
    tools_desc = "\n".join(details_of_tools)
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    sys_prompt = azure_devops_prompts["sys_prompt"](tools_desc)
    
    # Create initial state for the graph
    initial_state = ReactGraphState(
        tools=tools,
        azure_devops_tool_llm=llm_with_tools,
        workspace_id=workspace_id,
        user_id=user_id,
        conversation_id=conversation_id,
        messages=[SystemMessage(content=sys_prompt)]
    )
    
    try:
        # Set recursion limit to allow agent to retry errors a few times
        config = {"recursion_limit": 30}
        react_azure_devops_agent = get_react_azure_devops_agent()
        response = await react_azure_devops_agent.ainvoke(initial_state, config=config)
        azure_devops_response = response['messages'][-1].content
        
        # Save assistant response to session history
        server.session.append_message(
            workspace_id, user_id, conversation_id, 
            "assistant", azure_devops_response, job_id=job_id
        )
        
        return {
            "status": "success", 
            "role": "assistant", 
            "content": azure_devops_response
        }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in Azure DevOps agent execution: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Check if it's a recursion limit error
        if "recursion_limit" in error_msg.lower() or "maximum recursion" in error_msg.lower():
            return {
                "status": "error",
                "message": "The agent encountered multiple errors and reached the retry limit. "
                          "Please check your Azure DevOps configuration and try again."
            }
        
        return {
            "status": "error",
            "message": f"Error interacting with Azure DevOps: {error_msg}"
        }


@mcp.tool()
async def test_azure_devops_connection(
    workspace_id: str, 
    user_id: str, 
    data: dict[str, Any]
) -> dict[str, Any]:
    """
    This tool tests the Azure DevOps connection for the given workspace and user.
    
    Args:
        workspace_id: unique identifier for the workspace.
        user_id: unique identifier for the user.
        data: dictionary containing azure_devops_access_token, 
              azure_devops_organization, azure_devops_project, azure_devops_url.
    """
    return await test_ado_connection(
        workspace_id=workspace_id,
        user_id=user_id,
        data=data,
        azure_devops_client_class=AzureDevOps,
        user_config_manager=server.user_config_manager
    )


@mcp.tool()
async def toggle_azure_devops_connection(
    workspace_id: str, 
    user_id: str, 
    enable: bool
) -> dict[str, Any]:
    """
    This tool enables or disables the Azure DevOps connection for the given workspace and user.
    
    Args:
        workspace_id: unique identifier for the workspace.
        user_id: unique identifier for the user.
        enable: flag to enable or disable the connection.
    """
    return await toggle_ado_connection(
        workspace_id=workspace_id,
        user_id=user_id,
        enable=enable,
        azure_devops_client_manager=server.azure_devops_client_manager,
        user_config_manager=server.user_config_manager
    )
```

---

### Step 4: Update `main.py` - Import Tool

**File:** `agents/your_agent/main.py`

Add import for your new tool:
```python
# Import tools - this registers them with the MCP server
import tools.azure_devops_agent  # ADO integration
# ... other tool imports
```

---

### Step 5: Update Configuration Tool (Optional but Recommended)

**File:** `agents/your_agent/tools/config.py` (or similar config management file)

Add ADO config validation:

```python
from ado_tool_integration import azure_devops_update_config

@mcp.tool()
async def update_config(user_id: str, workspace_id: str, data: dict):
    """Update user configuration including ADO settings."""
    
    # Validate and normalize ADO config fields
    data = azure_devops_update_config(data)
    
    # Save to config manager
    server.user_config_manager.set_config(workspace_id, user_id, data)
    
    return {"status": "success", "message": "Configuration updated"}
```

---

### Step 6: Update Agent Chatbot - Add ADO Intent Classification

**File:** `agents/your_agent/tools/your_agent_chatbot.py` (or main chat handler)

Add intent classification for Azure DevOps requests:

```python
from tools.azure_devops_agent import azure_devops_agent

# In your intent classification prompt, add ADO scenarios


# After classification, route to ADO agent
if classification.lower() == "azure_devops":
    result = await azure_devops_agent(
        workspace_id=workspace_id,
        user_id=user_id,
        conversation_id=conversation_id
    )
    return result
```

---
