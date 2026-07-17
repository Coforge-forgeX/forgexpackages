# TrustAI Integration - Decoupling Changes

## Overview

Successfully decoupled the TrustAI Provider from the Database Manager to improve separation of concerns and enable more flexible usage patterns.

---

## What Changed

### Before (Coupled Architecture)
```
TrustAIProvider
    ↓ directly depends on
TrustAIDatabaseManager
    ↓ queries database
PostgreSQL
```

### After (Decoupled Architecture)
```
WorkspaceIntegration.get_provider_configuration()
    ↓ fetches credentials
Configuration Dict
    ↓ passed to
TrustAIProvider.from_configuration()
    ↓ uses credentials directly
TrustAI API
```

---

## Changes by Component

### 1. WorkspaceIntegration Class

**New Method Added:**
```python
def get_provider_configuration(
    workspace_id: str,
    agent_id: int,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get complete provider configuration for initializing TrustAI provider.
    
    Returns:
        {
            'workspace_config': {
                'x_app_id': str,
                'x_api_key': str,
                'api_endpoint': str
            },
            'provider_model': {
                'provider_name': str,
                'deployment_name': str,
                'trustai_model_key': str,
                'is_system_default': bool
            },
            'workspace_id': str,
            'agent_id': int,
            'user_id': Optional[int]
        }
    """
```

**Purpose:** Single method to fetch all credentials and configuration needed to initialize a provider.

---

### 2. TrustAIProvider Class

#### Changed Constructor

**Before:**
```python
def __init__(
    self,
    db_manager: TrustAIDatabaseManager,  # ❌ Database dependency
    workspace_id: str,
    agent_id: int,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None
):
    self.db = db_manager
    self.workspace_config = self.db.get_workspace_config(workspace_id)
    self.provider_model = self.db.resolve_provider_model(...)
```

**After:**
```python
def __init__(
    self,
    x_app_id: str,              # ✅ Direct credentials
    x_api_key: str,             # ✅ No database dependency
    api_endpoint: str,
    trustai_model_key: str,
    provider_name: str,
    deployment_name: str,
    workspace_id: str,
    agent_id: int,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None
):
    self.x_app_id = x_app_id
    self.x_api_key = x_api_key
    # ... uses credentials directly
```

#### New Factory Method

**Added:**
```python
@classmethod
def from_configuration(
    cls,
    config: Dict[str, Any],
    user_email: Optional[str] = None
) -> "TrustAIProvider":
    """
    Create provider from configuration dict.
    
    Recommended way to initialize the provider.
    Get config from WorkspaceIntegration.get_provider_configuration().
    """
```

**Usage:**
```python
# Step 1: Fetch configuration
integration = TrustAIWorkspaceIntegration(db_manager)
config = integration.get_provider_configuration(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)

# Step 2: Create provider (decoupled)
provider = TrustAIProvider.from_configuration(config)
```

---

### 3. TrustAILLMHelper Class

**Updated to use WorkspaceIntegration:**
```python
def __init__(self, database_url: str):
    self.db_manager = TrustAIDatabaseManager(database_url)
    self.db_manager.initialize_tables()
    self.integration = TrustAIWorkspaceIntegration(self.db_manager)  # ✅ New
```

**All methods now follow this pattern:**
```python
def get_llm_response(...):
    # 1. Fetch configuration
    config = self.integration.get_provider_configuration(
        workspace_id, agent_id, user_id
    )
    
    # 2. Create decoupled provider
    provider = TrustAIProvider.from_configuration(config, user_email)
    
    # 3. Use provider
    return await provider.generate_text(...)
```

**Updated methods:**
- ✅ `get_llm_response()`
- ✅ `get_llm_response_with_context()`
- ✅ `get_router_llm()`
- ✅ `get_provider()`

---

### 4. TrustAIChatModel (LangChain Adapter)

#### Changed Constructor

**Before:**
```python
def __init__(
    self,
    db_manager: TrustAIDatabaseManager,  # ❌ Database dependency
    workspace_id: str,
    agent_id: int,
    ...
):
    super().__init__(db_manager=db_manager, ...)
```

**After:**
```python
def __init__(
    self,
    config: Dict[str, Any],  # ✅ Configuration dict
    user_email: Optional[str] = None,
    ...
):
    super().__init__(
        config=config,
        workspace_id=config['workspace_id'],
        agent_id=config['agent_id'],
        ...
    )
```

#### Updated Provider Creation

**Before:**
```python
def _get_provider(self) -> TrustAIProvider:
    if self._provider is None:
        self._provider = TrustAIProvider(
            db_manager=self.db_manager,  # ❌ Database dependency
            ...
        )
```

**After:**
```python
def _get_provider(self) -> TrustAIProvider:
    if self._provider is None:
        self._provider = TrustAIProvider.from_configuration(
            config=self.config,  # ✅ Uses configuration
            user_email=self.user_email
        )
```

---

## Migration Guide

### Pattern 1: Direct Provider Usage

**Before:**
```python
from common_adapters.trustai import TrustAIDatabaseManager, TrustAIProvider

db_manager = TrustAIDatabaseManager(database_url)

# Old way - coupled
provider = TrustAIProvider(
    db_manager=db_manager,
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)
```

**After:**
```python
from common_adapters.trustai import (
    TrustAIDatabaseManager,
    TrustAIWorkspaceIntegration,
    TrustAIProvider
)

db_manager = TrustAIDatabaseManager(database_url)
integration = TrustAIWorkspaceIntegration(db_manager)

# New way - decoupled
config = integration.get_provider_configuration(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)
provider = TrustAIProvider.from_configuration(config)
```

### Pattern 2: LLM Helper (Recommended - No Changes Needed!)

```python
from common_adapters.trustai import get_llm_helper

# This still works exactly the same!
helper = get_llm_helper(database_url)

# All methods work the same
response = helper.get_llm_response(
    workspace_id="ws_123",
    agent_id=1,
    prompt="Hello",
    user_id=42
)

# LangChain integration works the same
llm = helper.get_router_llm(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)
```

**✅ If you're using `get_llm_helper()`, no code changes required!**

### Pattern 3: LangChain Direct Usage

**Before:**
```python
from common_adapters.trustai import TrustAIDatabaseManager, TrustAIChatModel

db_manager = TrustAIDatabaseManager(database_url)

llm = TrustAIChatModel(
    db_manager=db_manager,
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)
```

**After (Option 1 - Recommended):**
```python
from common_adapters.trustai import get_llm_helper

helper = get_llm_helper(database_url)
llm = helper.get_router_llm(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)
```

**After (Option 2 - Manual):**
```python
from common_adapters.trustai import (
    TrustAIDatabaseManager,
    TrustAIWorkspaceIntegration,
    TrustAIChatModel
)

db_manager = TrustAIDatabaseManager(database_url)
integration = TrustAIWorkspaceIntegration(db_manager)

config = integration.get_provider_configuration(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)

llm = TrustAIChatModel(config=config)
```

---

## Benefits of Decoupling

### 1. **Separation of Concerns**
- Provider focuses only on API communication
- Database operations isolated to WorkspaceIntegration
- Clear responsibility boundaries

### 2. **Testability**
```python
# Easy to test with mock configuration
mock_config = {
    'workspace_config': {
        'x_app_id': 'test-app-id',
        'x_api_key': 'test-api-key',
        'api_endpoint': 'https://test-api.com'
    },
    'provider_model': {
        'provider_name': 'azure',
        'deployment_name': 'gpt-4',
        'trustai_model_key': 'gpt-4'
    },
    'workspace_id': 'ws_test',
    'agent_id': 1
}

provider = TrustAIProvider.from_configuration(mock_config)
# No database needed for testing!
```

### 3. **Flexibility**
- Can create provider from config stored anywhere (cache, file, etc.)
- Easier to implement connection pooling
- Simpler to add alternative data sources

### 4. **Performance**
- Fetch config once, create multiple providers
- Reduce database queries
- Better caching opportunities

```python
# Fetch config once
config = integration.get_provider_configuration(ws_id, agent_id, user_id)

# Create multiple providers with different user_emails
provider1 = TrustAIProvider.from_configuration(config, user_email="user1@example.com")
provider2 = TrustAIProvider.from_configuration(config, user_email="user2@example.com")
```

### 5. **Cleaner Architecture**
```
┌─────────────────────┐
│  Application Layer  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   LLM Helper        │  ← Single entry point
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐  ┌──────────────┐
│Database │  │   Provider   │  ← Decoupled!
│ Layer   │  │   (API)      │
└─────────┘  └──────────────┘
```

---

## Backward Compatibility

### ✅ Fully Backward Compatible

All existing code using `get_llm_helper()` continues to work without changes:

```python
# This pattern still works perfectly!
from common_adapters.trustai import get_llm_helper

helper = get_llm_helper(database_url)

# All these work exactly as before
response = helper.get_llm_response(...)
response = helper.get_llm_response_with_context(...)
llm = helper.get_router_llm(...)
provider = helper.get_provider(...)
```

### ⚠️ Breaking Changes (Direct Usage Only)

Only affects code that directly instantiates `TrustAIProvider` or `TrustAIChatModel`:

**TrustAIProvider:**
- Old: `TrustAIProvider(db_manager, workspace_id, agent_id, ...)`
- New: `TrustAIProvider.from_configuration(config, ...)`

**TrustAIChatModel:**
- Old: `TrustAIChatModel(db_manager, workspace_id, agent_id, ...)`
- New: `TrustAIChatModel(config, ...)`

---

## Testing the Changes

### Unit Test Example

```python
import pytest
from common_adapters.trustai import TrustAIProvider

def test_provider_with_mock_config():
    """Test provider can be initialized without database."""
    
    # Mock configuration
    config = {
        'workspace_config': {
            'x_app_id': 'test-app-123',
            'x_api_key': 'test-key-xyz',
            'api_endpoint': 'https://test-trustai.com/api'
        },
        'provider_model': {
            'provider_name': 'azure',
            'deployment_name': 'gpt-4-test',
            'trustai_model_key': 'gpt-4-test',
            'is_system_default': True
        },
        'workspace_id': 'ws_test',
        'agent_id': 1,
        'user_id': 42
    }
    
    # Create provider without database
    provider = TrustAIProvider.from_configuration(
        config=config,
        user_email="test@example.com"
    )
    
    # Verify provider is initialized correctly
    assert provider.x_app_id == 'test-app-123'
    assert provider.x_api_key == 'test-key-xyz'
    assert provider.trustai_model_key == 'gpt-4-test'
    assert provider.workspace_id == 'ws_test'
    assert provider.agent_id == 1
    assert provider.user_email == 'test@example.com'
    
    # Verify model info
    info = provider.get_current_model_info()
    assert info['provider_name'] == 'azure'
    assert info['deployment_name'] == 'gpt-4-test'
```

### Integration Test Example

```python
async def test_full_integration():
    """Test complete flow from config fetch to LLM call."""
    
    # Setup
    db_manager = TrustAIDatabaseManager(database_url)
    integration = TrustAIWorkspaceIntegration(db_manager)
    
    # Fetch configuration
    config = integration.get_provider_configuration(
        workspace_id="ws_123",
        agent_id=1,
        user_id=42
    )
    
    # Create provider
    provider = TrustAIProvider.from_configuration(
        config=config,
        user_email="test@example.com"
    )
    
    # Call LLM
    response = await provider.generate_text(
        prompt="What is 2+2?",
        temperature=0.7,
        max_tokens=100
    )
    
    assert response is not None
    assert len(response) > 0
```

---

## Summary

### Key Improvements

✅ **Decoupled architecture** - Provider no longer depends on database  
✅ **Better testability** - Easy to mock configuration  
✅ **Improved flexibility** - Config can come from anywhere  
✅ **Cleaner separation** - Each component has clear responsibility  
✅ **Backward compatible** - Existing code using `get_llm_helper()` unchanged  
✅ **Better performance** - Reduced database queries  

### Files Modified

1. ✅ `workspace_integration.py` - Added `get_provider_configuration()`
2. ✅ `provider.py` - Refactored constructor, added `from_configuration()`
3. ✅ `llm_helper.py` - Updated to use WorkspaceIntegration
4. ✅ `langchain_adapter.py` - Updated to use configuration dict

### Recommended Usage

```python
# ✅ Best practice - Use LLM Helper
from common_adapters.trustai import get_llm_helper

helper = get_llm_helper(database_url)

# For simple calls
response = helper.get_llm_response(workspace_id, agent_id, prompt)

# For LangChain
llm = helper.get_router_llm(workspace_id, agent_id, user_id)
```

---

**Version:** 1.0.0-decoupled  
**Date:** 2026-07-17  
**Status:** Complete ✅
