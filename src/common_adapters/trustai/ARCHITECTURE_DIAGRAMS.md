# TrustAI Integration - Architecture Diagrams

Visual representation of the architectural changes from coupled to decoupled design.

---

## Before: Coupled Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        COUPLED ARCHITECTURE                          │
│                         (Before Changes)                             │
└─────────────────────────────────────────────────────────────────────┘

Application Code
      │
      │ Creates provider
      ▼
┌─────────────────────┐
│  TrustAIProvider    │
│  ─────────────────  │
│  - db_manager  ◄────┼──────────┐
│  - workspace_id     │          │ TIGHT COUPLING
│  - agent_id         │          │ Provider depends on DB
└──────────┬──────────┘          │
           │                     │
           │ Uses DB Manager     │
           │ for queries         │
           ▼                     │
┌──────────────────────┐         │
│ TrustAIDatabaseMgr   │◄────────┘
│ ───────────────────  │
│ - get_workspace_     │
│   config()           │
│ - resolve_provider_  │
│   model()            │
└──────────┬───────────┘
           │
           │ Queries
           ▼
     ┌──────────┐
     │PostgreSQL│
     └──────────┘


PROBLEMS:
─────────
❌ Provider tightly coupled to database
❌ Hard to test provider without database
❌ Cannot reuse configuration
❌ Multiple DB queries per provider instance
❌ Cannot use cached configurations
❌ Difficult to mock for testing
```

---

## After: Decoupled Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       DECOUPLED ARCHITECTURE                         │
│                         (After Changes)                              │
└─────────────────────────────────────────────────────────────────────┘

Application Code
      │
      │ Uses helper
      ▼
┌─────────────────────┐
│  TrustAILLMHelper   │  ← Recommended entry point
│  ─────────────────  │
│  - db_manager       │
│  - integration      │
└──────────┬──────────┘
           │
           │ Step 1: Fetch config
           ▼
┌──────────────────────────┐
│ TrustAIWorkspace         │
│ Integration              │
│ ───────────────────────  │
│ get_provider_            │
│ configuration()          │
└──────────┬───────────────┘
           │
           │ Queries DB once
           ▼
     ┌──────────┐
     │PostgreSQL│
     └──────────┘
           │
           │ Returns config dict
           ▼
     ┌─────────────────────────────┐
     │ Configuration Dict          │
     │ ───────────────────────────  │
     │ {                            │
     │   workspace_config: {...}    │
     │   provider_model: {...}      │
     │   workspace_id: "ws_123"     │
     │   agent_id: 1                │
     │ }                            │
     └──────────┬──────────────────┘
                │
                │ Step 2: Create provider
                ▼
     ┌──────────────────────┐
     │  TrustAIProvider     │
     │  ──────────────────  │
     │  - x_app_id          │  NO DATABASE
     │  - x_api_key         │  DEPENDENCY!
     │  - trustai_model_key │
     │  - provider_name     │
     └──────────┬───────────┘
                │
                │ Step 3: Call API
                ▼
          ┌──────────┐
          │ TrustAI  │
          │   API    │
          └──────────┘


BENEFITS:
─────────
✅ Provider decoupled from database
✅ Easy to test with mock config
✅ Configuration can be cached/reused
✅ Single DB query for multiple providers
✅ Clear separation of concerns
✅ Flexible configuration sources
```

---

## Data Flow Comparison

### Before: Multiple Database Queries

```
User Request
    │
    ├─► Create Provider 1 ──► Query DB ──► Get Config ──► Call API
    │
    ├─► Create Provider 2 ──► Query DB ──► Get Config ──► Call API
    │
    └─► Create Provider 3 ──► Query DB ──► Get Config ──► Call API

Total DB Queries: 3 × 2 = 6 queries
(2 queries per provider: workspace config + model resolution)
```

### After: Single Configuration Fetch

```
User Request
    │
    └─► Fetch Config ──► Query DB ──► Get Config
                                          │
                                          ├─► Create Provider 1 ──► Call API
                                          │
                                          ├─► Create Provider 2 ──► Call API
                                          │
                                          └─► Create Provider 3 ──► Call API

Total DB Queries: 2 queries
(Reuse same config for all providers)
```

---

## Component Interaction - Before

```
┌───────────────────────────────────────────────────────────────┐
│                    BEFORE: COUPLED FLOW                        │
└───────────────────────────────────────────────────────────────┘

┌────────────┐
│Application │
└─────┬──────┘
      │
      │ new TrustAIProvider(db_manager, ...)
      ▼
┌──────────────────────┐
│  TrustAIProvider     │
│  __init__()          │
└──────────┬───────────┘
           │
           ├─► self.db.get_workspace_config(workspace_id)
           │   └─► SELECT FROM trustai_workspace_config
           │
           └─► self.db.resolve_provider_model(workspace_id, agent_id, user_id)
               └─► SELECT FROM user_agent_provider_model_preference
               └─► SELECT FROM workspace_agent_provider_model_mapping  
               └─► SELECT FROM provider_models
           
Provider now has: workspace_config (ORM object) + provider_model (ORM object)

Problems:
• Provider holds DB connection references
• ORM objects tied to session lifecycle
• Hard to serialize/cache provider state
• Testing requires database setup
```

---

## Component Interaction - After

```
┌───────────────────────────────────────────────────────────────┐
│                    AFTER: DECOUPLED FLOW                       │
└───────────────────────────────────────────────────────────────┘

┌────────────┐
│Application │
└─────┬──────┘
      │
      │ helper.get_router_llm(...) / helper.get_llm_response(...)
      ▼
┌──────────────────────┐
│ TrustAILLMHelper     │
└──────────┬───────────┘
           │
           │ Step 1: Fetch configuration
           ▼
┌────────────────────────────┐
│ WorkspaceIntegration       │
│ get_provider_configuration │
└──────────┬─────────────────┘
           │
           ├─► db.get_workspace_config(workspace_id)
           │   └─► SELECT FROM trustai_workspace_config
           │
           ├─► db.resolve_provider_model(workspace_id, agent_id, user_id)
           │   └─► SELECT FROM user_agent_provider_model_preference
           │   └─► SELECT FROM workspace_agent_provider_model_mapping  
           │   └─► SELECT FROM provider_models
           │
           └─► Return pure dict (no ORM references)
               {
                 workspace_config: {...},
                 provider_model: {...},
                 workspace_id: "...",
                 agent_id: 1
               }
           
           │
           │ Step 2: Create provider
           ▼
┌──────────────────────────┐
│ TrustAIProvider          │
│ from_configuration()     │
└──────────┬───────────────┘
           │
           └─► Store plain values:
               - self.x_app_id = "..."
               - self.x_api_key = "..."
               - self.trustai_model_key = "..."
           
Provider now has: plain strings (no DB/ORM dependencies)

Benefits:
• Provider has no DB connection references
• Configuration is serializable dict
• Easy to cache/persist configuration
• Testing uses simple mock dicts
• Can reload provider from config
```

---

## Usage Pattern Comparison

### Pattern 1: Simple LLM Call

#### Before
```python
from common_adapters.trustai import TrustAIDatabaseManager, TrustAIProvider

db_manager = TrustAIDatabaseManager(database_url)

# Creates provider with DB dependency
provider = TrustAIProvider(
    db_manager=db_manager,  # ❌ DB Manager injected
    workspace_id="ws_123",
    agent_id=1
)
# Provider internally queries DB during __init__

response = await provider.generate_text("Hello")
```

#### After
```python
from common_adapters.trustai import get_llm_helper

# Recommended: Use helper (same API as before!)
helper = get_llm_helper(database_url)

response = helper.get_llm_response(
    workspace_id="ws_123",
    agent_id=1,
    prompt="Hello"
)
# ✅ Helper handles config fetch + provider creation internally
```

#### After (Manual)
```python
from common_adapters.trustai import (
    TrustAIDatabaseManager,
    TrustAIWorkspaceIntegration,
    TrustAIProvider
)

db_manager = TrustAIDatabaseManager(database_url)
integration = TrustAIWorkspaceIntegration(db_manager)

# Step 1: Fetch config (separate from provider)
config = integration.get_provider_configuration(
    workspace_id="ws_123",
    agent_id=1
)
# ✅ Config is a plain dict, no DB references

# Step 2: Create provider with config
provider = TrustAIProvider.from_configuration(config)
# ✅ Provider has no DB dependency

response = await provider.generate_text("Hello")
```

---

### Pattern 2: LangChain Integration

#### Before
```python
from common_adapters.trustai import TrustAIDatabaseManager, TrustAIChatModel

db_manager = TrustAIDatabaseManager(database_url)

llm = TrustAIChatModel(
    db_manager=db_manager,  # ❌ DB Manager injected
    workspace_id="ws_123",
    agent_id=1
)

from langchain_core.prompts import ChatPromptTemplate
prompt = ChatPromptTemplate.from_messages([...])
chain = prompt | llm
```

#### After
```python
from common_adapters.trustai import get_llm_helper

helper = get_llm_helper(database_url)

llm = helper.get_router_llm(
    workspace_id="ws_123",
    agent_id=1
)
# ✅ Returns TrustAIChatModel with config dict (no DB manager)

from langchain_core.prompts import ChatPromptTemplate
prompt = ChatPromptTemplate.from_messages([...])
chain = prompt | llm
```

---

### Pattern 3: Configuration Caching

#### Not Possible Before
```python
# ❌ Cannot cache configuration
# Each provider requires fresh DB manager
provider1 = TrustAIProvider(db_manager, ws_id, agent_id)
provider2 = TrustAIProvider(db_manager, ws_id, agent_id)
# Both query database independently
```

#### Now Possible After
```python
# ✅ Fetch config once, create multiple providers
integration = TrustAIWorkspaceIntegration(db_manager)

# Fetch once
config = integration.get_provider_configuration(
    workspace_id="ws_123",
    agent_id=1
)

# Cache config (Redis, memory, etc.)
cache.set("config:ws_123:agent_1", config)

# Reuse config for multiple providers
provider1 = TrustAIProvider.from_configuration(config)
provider2 = TrustAIProvider.from_configuration(config)
provider3 = TrustAIProvider.from_configuration(config)

# ✅ Zero additional DB queries!
```

---

## Testing Comparison

### Testing Before (Complicated)

```python
# ❌ Requires full database setup for testing

import pytest
from common_adapters.trustai import TrustAIDatabaseManager, TrustAIProvider

@pytest.fixture
def setup_database():
    """Complex setup required"""
    # Create test database
    # Initialize tables
    # Seed test data
    # ...
    db_manager = TrustAIDatabaseManager(test_db_url)
    return db_manager

def test_provider(setup_database):
    db_manager = setup_database
    
    # Still requires valid DB data
    provider = TrustAIProvider(
        db_manager=db_manager,
        workspace_id="test_ws",
        agent_id=1
    )
    
    # Test...
```

### Testing After (Simple)

```python
# ✅ No database required for provider testing

import pytest
from common_adapters.trustai import TrustAIProvider

def test_provider():
    """Simple test with mock config"""
    
    # Just create a config dict
    mock_config = {
        'workspace_config': {
            'x_app_id': 'test-app',
            'x_api_key': 'test-key',
            'api_endpoint': 'https://test.com/api'
        },
        'provider_model': {
            'provider_name': 'azure',
            'deployment_name': 'gpt-4',
            'trustai_model_key': 'gpt-4'
        },
        'workspace_id': 'test_ws',
        'agent_id': 1
    }
    
    # Create provider without database!
    provider = TrustAIProvider.from_configuration(mock_config)
    
    # Test provider logic
    assert provider.x_app_id == 'test-app'
    assert provider.trustai_model_key == 'gpt-4'
    
    # Can test header building, payload creation, etc.
    headers = provider._build_headers()
    assert headers['X-App-Id'] == 'test-app'
```

---

## Architecture Summary

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  - Product Owner Agent                                       │
│  - Other AI Agents                                           │
│  - API Endpoints                                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Uses
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FACADE LAYER                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  TrustAILLMHelper                                    │   │
│  │  - get_llm_response()                                │   │
│  │  - get_llm_response_with_context()                   │   │
│  │  - get_router_llm()                                  │   │
│  └─────────────────────────────────────────────────────┘   │
└────────┬──────────────────────┬─────────────────────────────┘
         │                      │
         │ Creates              │ Creates
         ▼                      ▼
┌──────────────────┐   ┌─────────────────────┐
│INTEGRATION LAYER │   │  PROVIDER LAYER     │
│                  │   │                     │
│WorkspaceIntegr.  │   │  TrustAIProvider    │
│- get_provider_   │   │  - generate_text()  │
│  configuration() │   │  - chat_completion()│
└────────┬─────────┘   └──────────┬──────────┘
         │                        │
         │ Queries                │ Calls
         ▼                        ▼
┌──────────────────┐   ┌─────────────────────┐
│  DATABASE LAYER  │   │   TRUSTAI API       │
│                  │   │                     │
│ TrustAIDatabase  │   │  /chat/completions  │
│ Manager          │   │  /admin/apps        │
└──────────────────┘   └─────────────────────┘
         │
         │ Connects
         ▼
   ┌──────────┐
   │PostgreSQL│
   └──────────┘

SEPARATION OF CONCERNS:
───────────────────────
• Application → Uses Facade
• Facade → Orchestrates Integration + Provider
• Integration → Manages configuration & DB
• Provider → Handles API communication only
• No cross-dependencies between Integration & Provider
```

---

## Key Architectural Principles

### 1. Single Responsibility
- **WorkspaceIntegration**: Manages workspace registration & configuration
- **DatabaseManager**: Handles database operations
- **Provider**: Handles TrustAI API communication
- **LLMHelper**: Provides convenient facade

### 2. Dependency Inversion
- Provider depends on configuration interface (dict), not database implementation
- Easy to swap data sources

### 3. Open/Closed Principle
- Open for extension: Can add new configuration sources
- Closed for modification: Provider doesn't change when DB schema changes

### 4. Interface Segregation
- Provider only gets what it needs (credentials), not entire database access

---

**Version:** 1.0.0  
**Date:** 2026-07-17  
**Status:** Architectural Documentation Complete ✅
