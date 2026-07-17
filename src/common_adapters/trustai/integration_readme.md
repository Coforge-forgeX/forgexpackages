# TrustAI Integration - Flow Documentation

Complete visualization and documentation of the TrustAI integration flow from workspace registration through final LLM calling.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Complete Integration Flow](#complete-integration-flow)
3. [Workspace Registration Flow](#workspace-registration-flow)
4. [Model Resolution Hierarchy](#model-resolution-hierarchy)
5. [LLM Calling Flow](#llm-calling-flow)
6. [Component Interaction](#component-interaction)
7. [Database Schema and Relationships](#database-schema-and-relationships)
8. [Usage Patterns](#usage-patterns)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TrustAI Integration Layer                        │
│                                                                           │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   LLM Helper  │  │  LangChain   │  │  Workspace  │  │   TrustAI   │ │
│  │   (Facade)    │  │   Adapter    │  │ Integration │  │   Provider  │ │
│  └───────┬───────┘  └──────┬───────┘  └──────┬──────┘  └──────┬──────┘ │
│          │                  │                  │                 │        │
│          └──────────────────┴──────────────────┴─────────────────┘        │
│                                      │                                     │
│                          ┌───────────▼──────────┐                         │
│                          │  Database Manager    │                         │
│                          │   (SQLAlchemy ORM)   │                         │
│                          └───────────┬──────────┘                         │
└──────────────────────────────────────┼──────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
            ┌───────▼────────┐ ┌──────▼──────┐  ┌───────▼────────┐
            │   PostgreSQL    │ │  TrustAI    │  │   LangChain    │
            │    Database     │ │     API     │  │   Framework    │
            └─────────────────┘ └─────────────┘  └────────────────┘
```

### Key Components

| Component | Purpose | Entry Point |
|-----------|---------|-------------|
| **LLM Helper** | Facade for all LLM operations | `get_llm_helper(database_url)` |
| **Database Manager** | Database operations & ORM | `TrustAIDatabaseManager(database_url)` |
| **Workspace Integration** | Registration & configuration | `TrustAIWorkspaceIntegration(db_manager)` |
| **TrustAI Provider** | Direct API communication | `TrustAIProvider(...)` |
| **LangChain Adapter** | LangChain compatibility | `TrustAIChatModel(...)` |

---

## Complete Integration Flow

### High-Level Flow Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE TRUSTAI INTEGRATION FLOW                    │
└────────────────────────────────────────────────────────────────────────┘

PHASE 1: INITIALIZATION & SETUP
════════════════════════════════
┌─────────────────────┐
│ 1. Database Setup   │
│ Initialize Tables   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Provider Models  │
│ Configure Available │
│ Models & Defaults   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Workspace        │
│ Registration with   │
│ TrustAI API         │
└──────────┬──────────┘
           │
═══════════▼═════════════════════════════════════════

PHASE 2: RUNTIME CONFIGURATION
═══════════════════════════════
           │
           ▼
┌─────────────────────┐
│ 4. Agent-Level      │
│ Model Configuration │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. User Preferences │
│ (Optional)          │
└──────────┬──────────┘
           │
═══════════▼═════════════════════════════════════════

PHASE 3: LLM EXECUTION
═══════════════════════
           │
           ▼
┌─────────────────────┐
│ 6. Model Resolution │
│ User→Agent→System   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 7. LLM Call via     │
│ TrustAI API         │
│ (with Guardrails)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 8. Response Return  │
│ to Application      │
└─────────────────────┘
```

---

## Workspace Registration Flow

### Detailed Registration Sequence

```
┌──────────┐                ┌────────────────────┐              ┌─────────────┐
│   User   │                │ WorkspaceIntegration│              │  TrustAI    │
│  /App    │                │      Component      │              │    API      │
└────┬─────┘                └──────────┬─────────┘              └──────┬──────┘
     │                                  │                                │
     │ 1. register_workspace()         │                                │
     │  ┌─────────────────────────┐    │                                │
     │  │ - workspace_id          │    │                                │
     │  │ - trustai_config        │    │                                │
     │  │   ├─ application info   │    │                                │
     │  │   ├─ guardrails list    │    │                                │
     │  │   └─ system_config      │    │                                │
     │  └─────────────────────────┘    │                                │
     ├─────────────────────────────────▶                                │
     │                                  │                                │
     │                                  │ 2. POST /trustai-api/admin/apps
     │                                  │    (with MASTER_API_KEY)       │
     │                                  ├───────────────────────────────▶
     │                                  │                                │
     │                                  │ 3. ◀── app_id (UUID)           │
     │                                  ◀────────────────────────────────┤
     │                                  │                                │
     │                                  │ 4. POST /api/v1/api-keys/      │
     │                                  │    ┌──────────────────────┐   │
     │                                  │    │ user_id: app_id      │   │
     │                                  │    │ lifetime_days: 365   │   │
     │                                  │    └──────────────────────┘   │
     │                                  ├───────────────────────────────▶
     │                                  │                                │
     │                                  │ 5. ◀── api_key (string)        │
     │                                  ◀────────────────────────────────┤
     │                                  │                                │
     │                                  │ 6. Save to Database            │
     │                                  │  ┌───────────────────────┐    │
     │                                  │  │ trustai_workspace_    │    │
     │                                  │  │ config table:         │    │
     │                                  │  │ - workspace_id        │    │
     │                                  │  │ - x_app_id            │    │
     │                                  │  │ - x_api_key           │    │
     │                                  │  │ - api_endpoint        │    │
     │                                  │  └───────────────────────┘    │
     │                                  │                                │
     │                                  │ 7. Initialize default          │
     │                                  │    agent configs               │
     │                                  │    (using system default)      │
     │                                  │                                │
     │ 8. ◀── (app_id, api_key)        │                                │
     ◀─────────────────────────────────┤                                │
     │                                  │                                │
```

### Registration Code Flow

```python
# Step-by-step breakdown

# STEP 1: Initialize Database Manager
database_manager = TrustAIDatabaseManager(database_url)
database_manager.initialize_tables()

# STEP 2: Create Workspace Integration
integration = TrustAIWorkspaceIntegration(database_manager)

# STEP 3: Prepare TrustAI Configuration
trustai_config = {
    "application": {
        "name": "My Workspace",
        "description": "Workspace description",
        "line_of_business": "technology",
        "technical_architect": "tech@example.com",
        "business_sponsor": "business@example.com"
    },
    "guardrails": ["BSI_DETECTION", "TOXIC", "PII", "PROMPT_INJECTION"],
    "system_config": {
        "guardrail_model": "llama-4-scout",
        "admin_emails": ["admin@example.com"],
        "is_guardrail_notification_enabled": True,
        "input_guardrail_execution_mode": "sync",
        "output_guardrail_execution_mode": "sync"
    }
}

# STEP 4: Register Workspace (internally makes 2 API calls)
app_id, api_key = await integration.register_workspace(
    workspace_id="ws_123",
    trustai_config=trustai_config
)

# Behind the scenes:
# 4a. POST to /trustai-api/admin/apps → returns app_id
# 4b. POST to /api/v1/api-keys/ → returns api_key
# 4c. Save to database: trustai_workspace_config table
# 4d. Initialize default agent configurations
```

---

## Model Resolution Hierarchy

### Three-Tier Resolution System

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MODEL RESOLUTION HIERARCHY                           │
│                                                                           │
│  Priority: User Preference → Agent Default → System Default              │
└─────────────────────────────────────────────────────────────────────────┘

TIER 1: USER-SPECIFIC PREFERENCE (Highest Priority)
════════════════════════════════════════════════════
┌──────────────────────────────────────────────────────┐
│ user_agent_provider_model_preference                 │
│ ─────────────────────────────────────────────────    │
│ • workspace_id: "ws_123"                             │
│ • user_id: 42                                        │
│ • agent_id: 1                                        │
│ • provider_model_id: 10                              │
│                                                       │
│ ✓ If exists → USE THIS MODEL                         │
│ ✗ If not exists → Check TIER 2                       │
└──────────────────────────────────────────────────────┘
                         ▼
TIER 2: WORKSPACE-AGENT DEFAULT
════════════════════════════════
┌──────────────────────────────────────────────────────┐
│ workspace_agent_provider_model_mapping               │
│ ─────────────────────────────────────────────────    │
│ • workspace_id: "ws_123"                             │
│ • agent_id: 1                                        │
│ • provider_model_id: 5                               │
│ • is_default: TRUE                                   │
│                                                       │
│ ✓ If exists & is_default=true → USE THIS MODEL       │
│ ✗ If not exists → Check TIER 3                       │
└──────────────────────────────────────────────────────┘
                         ▼
TIER 3: SYSTEM DEFAULT (Fallback)
══════════════════════════════════
┌──────────────────────────────────────────────────────┐
│ provider_models                                       │
│ ─────────────────────────────────────────────────    │
│ • provider_name: "azure"                             │
│ • deployment_name: "gpt-4-1"                         │
│ • trustai_model_key: "gpt-4-1"                       │
│ • is_system_default: TRUE                            │
│ • is_active: TRUE                                    │
│                                                       │
│ ✓ Must exist → USE THIS MODEL                        │
│ ✗ If not exists → ERROR: No model configured         │
└──────────────────────────────────────────────────────┘
```

### Resolution Code Path

```python
def resolve_provider_model(
    workspace_id: str,
    agent_id: int,
    user_id: Optional[int] = None
) -> Optional[ProviderModel]:
    """
    Resolves provider model using 3-tier hierarchy.
    """
    with self.get_session() as session:
        
        # TIER 1: Check user-specific preference
        if user_id:
            user_pref = session.query(
                UserAgentProviderModelPreference
            ).filter_by(
                workspace_id=workspace_id,
                user_id=user_id,
                agent_id=agent_id
            ).first()
            
            if user_pref:
                return user_pref.provider_model  # ✓ FOUND
        
        # TIER 2: Check workspace-agent default
        agent_mapping = session.query(
            WorkspaceAgentProviderModelMapping
        ).filter_by(
            workspace_id=workspace_id,
            agent_id=agent_id,
            is_default=True
        ).first()
        
        if agent_mapping:
            return agent_mapping.provider_model  # ✓ FOUND
        
        # TIER 3: Use system default
        system_default = session.query(
            ProviderModel
        ).filter_by(
            is_system_default=True,
            is_active=True
        ).first()
        
        return system_default  # ✓ FOUND or None
```

---

## LLM Calling Flow

### Complete LLM Invocation Sequence

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     LLM CALLING FLOW (END-TO-END)                         │
└──────────────────────────────────────────────────────────────────────────┘

┌────────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐     ┌─────────┐
│Application │     │   LLM    │     │ Provider │     │Database │     │TrustAI  │
│   Code     │     │  Helper  │     │Component │     │ Manager │     │  API    │
└─────┬──────┘     └────┬─────┘     └────┬─────┘     └────┬────┘     └────┬────┘
      │                 │                 │                 │                │
      │ get_llm_response()                │                 │                │
      │  - workspace_id                   │                 │                │
      │  - agent_id                       │                 │                │
      │  - prompt                         │                 │                │
      │  - user_id (optional)             │                 │                │
      ├────────────────▶                  │                 │                │
      │                 │                 │                 │                │
      │                 │ Create Provider │                 │                │
      │                 │ Instance        │                 │                │
      │                 ├────────────────▶                  │                │
      │                 │                 │                 │                │
      │                 │                 │ Get Workspace   │                │
      │                 │                 │ Config          │                │
      │                 │                 ├────────────────▶                │
      │                 │                 │                 │                │
      │                 │                 │ ◀── Config      │                │
      │                 │                 │  (app_id,       │                │
      │                 │                 │   api_key)      │                │
      │                 │                 ◀─────────────────┤                │
      │                 │                 │                 │                │
      │                 │                 │ Resolve Model   │                │
      │                 │                 │ (3-tier lookup) │                │
      │                 │                 ├────────────────▶                │
      │                 │                 │                 │                │
      │                 │                 │ ◀── Model Info  │                │
      │                 │                 │  (provider,     │                │
      │                 │                 │   deployment,   │                │
      │                 │                 │   trustai_key)  │                │
      │                 │                 ◀─────────────────┤                │
      │                 │                 │                 │                │
      │                 │ ◀── Provider    │                 │                │
      │                 │     Ready       │                 │                │
      │                 ◀─────────────────┤                 │                │
      │                 │                 │                 │                │
      │                 │ generate_text() │                 │                │
      │                 ├────────────────▶                  │                │
      │                 │                 │                 │                │
      │                 │                 │ Build Headers:  │                │
      │                 │                 │  - X-Api-Key    │                │
      │                 │                 │  - X-App-Id     │                │
      │                 │                 │  - X-Agent-Id   │                │
      │                 │                 │  - X-User-Id    │                │
      │                 │                 │                 │                │
      │                 │                 │ Build Payload:  │                │
      │                 │                 │  - messages     │                │
      │                 │                 │  - model (key)  │                │
      │                 │                 │  - temperature  │                │
      │                 │                 │  - max_tokens   │                │
      │                 │                 │                 │                │
      │                 │                 │ POST /trustai-api/ai-gateway/   │
      │                 │                 │      chat/completions            │
      │                 │                 ├─────────────────────────────────▶
      │                 │                 │                 │                │
      │                 │                 │         ┌────────────────────┐  │
      │                 │                 │         │  TrustAI Processing│  │
      │                 │                 │         │  ────────────────  │  │
      │                 │                 │         │ 1. Input Guardrails│  │
      │                 │                 │         │ 2. LLM Generation  │  │
      │                 │                 │         │ 3. Output Guards   │  │
      │                 │                 │         └────────────────────┘  │
      │                 │                 │                 │                │
      │                 │                 │ ◀── Response    │                │
      │                 │                 │  {              │                │
      │                 │                 │    choices: [{  │                │
      │                 │                 │      message: { │                │
      │                 │                 │        content  │                │
      │                 │                 │      }          │                │
      │                 │                 │    }]           │                │
      │                 │                 │  }              │                │
      │                 │                 ◀─────────────────────────────────┤
      │                 │                 │                 │                │
      │                 │ ◀── Text        │                 │                │
      │                 │     Response    │                 │                │
      │                 ◀─────────────────┤                 │                │
      │                 │                 │                 │                │
      │ ◀── Response    │                 │                 │                │
      ◀─────────────────┤                 │                 │                │
      │                 │                 │                 │                │
```

### Request/Response Details

#### Request to TrustAI API

```http
POST /trustai-api/ai-gateway/chat/completions
Content-Type: application/json
X-Api-Key: {api_key_from_workspace_config}
X-App-Id: {app_id_from_workspace_config}
X-Agent-Id: {agent_id}
X-User-Id: {user_email_or_user_id}

{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "What is artificial intelligence?"}
  ],
  "model": "gpt-4-1",  // trustai_model_key from resolved provider
  "temperature": 0.7,
  "max_tokens": 1000,
  "top_p": 0.9
}
```

#### Response from TrustAI API

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4-1",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Artificial intelligence (AI) refers to..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 100,
    "total_tokens": 115
  }
}
```

---

## Component Interaction

### Detailed Component Collaboration

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   COMPONENT INTERACTION DIAGRAM                          │
└─────────────────────────────────────────────────────────────────────────┘

APPLICATION LAYER
═════════════════
┌──────────────────────────────────────────┐
│          User Application Code            │
│  ┌────────────────────────────────────┐  │
│  │ from common_adapters.trustai       │  │
│  │ import get_llm_helper               │  │
│  │                                     │  │
│  │ helper = get_llm_helper(db_url)    │  │
│  │ response = helper.get_llm_response │  │
│  └────────────────────────────────────┘  │
└───────────────────┬──────────────────────┘
                    │
                    │ Uses
                    ▼
FACADE LAYER
════════════
┌──────────────────────────────────────────┐
│         TrustAILLMHelper                  │
│  ┌────────────────────────────────────┐  │
│  │ • get_llm_response()               │  │
│  │ • get_llm_response_with_context()  │  │
│  │ • get_router_llm()                 │  │
│  │ • get_provider()                   │  │
│  └────────────────────────────────────┘  │
└───────┬──────────────────┬───────────────┘
        │                  │
        │ Creates          │ Creates
        ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│  TrustAIProvider │  │ TrustAIChatModel │
│                  │  │ (LangChain)      │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         │ Uses                │ Uses
         ▼                     ▼
INTEGRATION LAYER
═════════════════
┌──────────────────────────────────────────┐
│      TrustAIDatabaseManager              │
│  ┌────────────────────────────────────┐  │
│  │ • get_workspace_config()           │  │
│  │ • resolve_provider_model()         │  │
│  │ • get_session()                    │  │
│  └────────────────────────────────────┘  │
└───────────────────┬──────────────────────┘
                    │
                    │ Queries
                    ▼
DATA LAYER
══════════
┌─────────────────────────────────────────────┐
│          PostgreSQL Database                 │
│  ┌───────────────────────────────────────┐  │
│  │ • trustai_workspace_config           │  │
│  │ • provider_models                    │  │
│  │ • workspace_agent_provider_mapping   │  │
│  │ • user_agent_provider_preference     │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘

EXTERNAL API
════════════
┌─────────────────────────────────────────────┐
│            TrustAI REST API                  │
│  ┌───────────────────────────────────────┐  │
│  │ • /admin/apps (registration)         │  │
│  │ • /api-keys/ (key management)        │  │
│  │ • /chat/completions (LLM calls)      │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## Database Schema and Relationships

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATABASE SCHEMA (ERD)                             │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────┐
│ trustai_workspace_config             │
│ ──────────────────────────────────── │
│ PK  id (serial)                      │
│ UK  workspace_id (uuid string)       │
│     x_app_id (varchar)               │◀────┐
│     x_api_key (varchar)              │     │
│     api_endpoint (text)              │     │
│     created_at (timestamp)           │     │
│     updated_at (timestamp)           │     │
└──────────────────────────────────────┘     │
                                              │
                                              │ Used for
                                              │ API calls
                                              │
┌──────────────────────────────────────┐     │
│ provider_models                      │     │
│ ──────────────────────────────────── │     │
│ PK  id (serial)                      │     │
│ UK  (provider_name, deployment_name) │     │
│     provider_name (varchar)          │     │
│     deployment_name (varchar)        │     │
│     trustai_model_key (varchar)      │─────┘
│     is_system_default (boolean)      │  Sent to
│     is_active (boolean)              │  TrustAI API
│     created_at (timestamp)           │
└────────────┬─────────────────────────┘
             │
             │ Referenced by
             │ (FK)
             │
  ┌──────────┴────────────┬──────────────────────┐
  │                       │                      │
  ▼                       ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│ workspace_agent_provider_model_mapping                      │
│ ─────────────────────────────────────────────────────────── │
│ PK  id (serial)                                             │
│ UK  (workspace_id, agent_id, provider_model_id)             │
│ FK  provider_model_id → provider_models.id                  │
│     workspace_id (uuid string)                              │
│     agent_id (integer)                                      │
│     is_default (boolean)                                    │
│     created_by (integer, optional)                          │
│     created_at (timestamp)                                  │
└─────────────────────────────────────────────────────────────┘
              ▲
              │
              │ TIER 2 Resolution
              │
┌─────────────────────────────────────────────────────────────┐
│ user_agent_provider_model_preference                        │
│ ─────────────────────────────────────────────────────────── │
│ PK  id (serial)                                             │
│ UK  (workspace_id, user_id, agent_id)                       │
│ FK  provider_model_id → provider_models.id                  │
│     workspace_id (uuid string)                              │
│     user_id (integer)                                       │
│     agent_id (integer)                                      │
│     created_at (timestamp)                                  │
│     updated_at (timestamp)                                  │
└─────────────────────────────────────────────────────────────┘
              ▲
              │
              │ TIER 1 Resolution (Highest Priority)
              │
```

### Table Relationships

```
RELATIONSHIP GRAPH
══════════════════

trustai_workspace_config
    ↓ (1:N - not enforced by FK, logical relationship)
    workspace_id used in ↓
    ↓
workspace_agent_provider_model_mapping
    ├─→ (N:1) provider_models
    └─→ workspace + agent configuration
    
workspace_agent_provider_model_mapping
    ↓ (logical relationship via workspace_id + agent_id)
    ↓
user_agent_provider_model_preference
    └─→ (N:1) provider_models

RESOLUTION CHAIN
════════════════
user_agent_provider_model_preference.provider_model_id
    ↓ if not found
workspace_agent_provider_model_mapping.provider_model_id (where is_default=true)
    ↓ if not found
provider_models (where is_system_default=true)
```

---

## Usage Patterns

### Pattern 1: Simple Text Generation

```python
┌─────────────────────────────────────────────────────────────┐
│ PATTERN 1: Simple Text Generation                           │
└─────────────────────────────────────────────────────────────┘

from common_adapters.trustai import get_llm_helper

# Initialize helper (cached singleton)
helper = get_llm_helper(database_url)

# Simple generation
response = helper.get_llm_response(
    workspace_id="ws_123",
    agent_id=1,
    prompt="What is artificial intelligence?",
    user_id=42,
    user_email="user@example.com"
)

print(response)

EXECUTION FLOW:
───────────────
1. Helper retrieves/creates TrustAIDatabaseManager
2. Creates TrustAIProvider instance
3. Provider loads workspace config from DB
4. Provider resolves model (3-tier hierarchy)
5. Provider builds request with headers
6. POST to TrustAI /chat/completions
7. Return parsed response content
```

### Pattern 2: Context-Aware Conversation

```python
┌─────────────────────────────────────────────────────────────┐
│ PATTERN 2: Context-Aware Conversation                       │
└─────────────────────────────────────────────────────────────┘

from common_adapters.trustai import get_llm_helper

helper = get_llm_helper(database_url)

# Conversation with history
conversation_history = [
    {"role": "user", "content": "Hi, I'm working on a Python project"},
    {"role": "assistant", "content": "Hello! I'd be happy to help with Python."}
]

response = helper.get_llm_response_with_context(
    workspace_id="ws_123",
    agent_id=1,
    sys_prompt="You are a Python expert assistant",
    user_input="How do I handle async operations?",
    history=conversation_history,
    user_id=42
)

print(response)

EXECUTION FLOW:
───────────────
1. Helper creates TrustAIProvider
2. Provider builds messages array:
   - System message with sys_prompt
   - All history messages
   - New user message
3. POST to TrustAI with full context
4. Return response (maintains conversation flow)
```

### Pattern 3: LangChain Integration

```python
┌─────────────────────────────────────────────────────────────┐
│ PATTERN 3: LangChain Integration                            │
└─────────────────────────────────────────────────────────────┘

from common_adapters.trustai import get_llm_helper
from langchain_core.prompts import ChatPromptTemplate

# Get LangChain-compatible LLM
helper = get_llm_helper(database_url)
llm = helper.get_router_llm(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)

# Use in LangChain chain
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful coding assistant"),
    ("user", "{input}")
])

chain = prompt | llm
response = chain.invoke({"input": "Explain list comprehensions"})

print(response.content)

EXECUTION FLOW:
───────────────
1. Helper creates TrustAIChatModel (extends BaseChatModel)
2. TrustAIChatModel wraps TrustAIProvider
3. LangChain chain.invoke() calls model._generate()
4. Model converts LangChain messages to TrustAI format
5. Delegates to TrustAIProvider
6. Returns wrapped AIMessage
```

### Pattern 4: LangGraph Agent with Tools

```python
┌─────────────────────────────────────────────────────────────┐
│ PATTERN 4: LangGraph Agent with Tools                       │
└─────────────────────────────────────────────────────────────┘

from common_adapters.trustai import get_llm_helper
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Define tools
@tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Weather in {location}: Sunny, 72°F"

@tool
def search_web(query: str) -> str:
    """Search the web."""
    return f"Search results for: {query}"

# Get LLM with tool support
helper = get_llm_helper(database_url)
llm = helper.get_router_llm(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)

# Create LangGraph agent
tools = [get_weather, search_web]
agent = create_react_agent(llm, tools)

# Execute
result = agent.invoke({
    "messages": [("user", "What's the weather in San Francisco?")]
})

print(result["messages"][-1].content)

EXECUTION FLOW:
───────────────
1. LangGraph binds tools to TrustAIChatModel
2. Model's bind_tools() converts tools to OpenAI format
3. Agent invokes with tools parameter
4. Model._agenerate() detects tools in kwargs
5. Calls provider.chat_completion_with_tools()
6. TrustAI API receives tools in request
7. Returns tool_calls if LLM wants to use tools
8. Agent executes tools and continues loop
```

### Pattern 5: Structured Output

```python
┌─────────────────────────────────────────────────────────────┐
│ PATTERN 5: Structured Output with Pydantic                  │
└─────────────────────────────────────────────────────────────┘

from common_adapters.trustai import get_llm_helper
from pydantic import BaseModel, Field

# Define output schema
class PersonInfo(BaseModel):
    name: str = Field(description="Person's full name")
    age: int = Field(description="Person's age in years")
    occupation: str = Field(description="Person's job title")
    skills: list[str] = Field(description="List of skills")

# Get LLM
helper = get_llm_helper(database_url)
llm = helper.get_router_llm(
    workspace_id="ws_123",
    agent_id=1,
    user_id=42
)

# Get structured output
structured_llm = llm.with_structured_output(PersonInfo)
result = structured_llm.invoke(
    "Tell me about John, a 30 year old software engineer who knows Python and SQL"
)

print(f"Name: {result.name}")
print(f"Age: {result.age}")
print(f"Occupation: {result.occupation}")
print(f"Skills: {', '.join(result.skills)}")

EXECUTION FLOW:
───────────────
1. with_structured_output() converts schema to function
2. Binds function as forced tool call
3. Model invokes with tool_choice forcing the schema
4. TrustAI API returns tool_call with structured data
5. LangChain parses and validates against Pydantic model
6. Returns typed Pydantic instance
```

---

## Complete Workflow Example

### End-to-End Integration Script

```python
┌─────────────────────────────────────────────────────────────────────────┐
│              COMPLETE END-TO-END INTEGRATION EXAMPLE                     │
└─────────────────────────────────────────────────────────────────────────┘

import asyncio
from common_adapters.trustai import (
    TrustAIDatabaseManager,
    TrustAIWorkspaceIntegration,
    get_llm_helper
)

async def complete_integration_example():
    """
    Complete example showing all steps from setup to LLM calling.
    """
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: DATABASE INITIALIZATION
    # ═══════════════════════════════════════════════════════════════
    
    print("Phase 1: Initializing database...")
    database_url = "postgresql://user:pass@localhost:5432/forgex"
    
    # Create database manager
    db_manager = TrustAIDatabaseManager(database_url)
    
    # Initialize tables (auto-creates if not exist)
    db_manager.initialize_tables()
    print("✓ Database initialized")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: PROVIDER MODEL CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    
    print("\nPhase 2: Configuring provider models...")
    
    # Add provider models
    gpt4_model = db_manager.create_provider_model(
        provider_name="azure",
        deployment_name="gpt-4-1",
        trustai_model_key="gpt-4-1",
        is_system_default=True  # Set as system default
    )
    
    gpt35_model = db_manager.create_provider_model(
        provider_name="azure",
        deployment_name="gpt-35-turbo",
        trustai_model_key="gpt-35-turbo",
        is_system_default=False
    )
    
    print("✓ Provider models configured")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 3: WORKSPACE REGISTRATION
    # ═══════════════════════════════════════════════════════════════
    
    print("\nPhase 3: Registering workspace with TrustAI...")
    
    integration = TrustAIWorkspaceIntegration(db_manager)
    
    # Prepare TrustAI config
    trustai_config = {
        "application": {
            "name": "ProductOwner Agent Workspace",
            "description": "AI-powered product management workspace",
            "line_of_business": "technology",
            "technical_architect": "tech@coforge.com",
            "business_sponsor": "business@coforge.com"
        },
        "guardrails": [
            "BSI_DETECTION",
            "TOXIC",
            "PII",
            "PROMPT_INJECTION"
        ],
        "system_config": {
            "guardrail_model": "llama-4-scout",
            "admin_emails": ["admin@coforge.com"],
            "is_guardrail_notification_enabled": True,
            "input_guardrail_execution_mode": "sync",
            "output_guardrail_execution_mode": "sync"
        }
    }
    
    # Register workspace
    workspace_id = "550e8400-e29b-41d4-a716-446655440000"
    app_id, api_key = await integration.register_workspace(
        workspace_id=workspace_id,
        trustai_config=trustai_config
    )
    
    print(f"✓ Workspace registered: app_id={app_id}")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 4: AGENT-LEVEL CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    
    print("\nPhase 4: Configuring agent-level models...")
    
    # Configure Agent 1 to use GPT-4
    integration.configure_agent_provider_model(
        workspace_id=workspace_id,
        agent_id=1,
        provider_name="azure",
        deployment_name="gpt-4-1",
        created_by=100
    )
    
    # Configure Agent 2 to use GPT-3.5
    integration.configure_agent_provider_model(
        workspace_id=workspace_id,
        agent_id=2,
        provider_name="azure",
        deployment_name="gpt-35-turbo",
        created_by=100
    )
    
    print("✓ Agent configurations set")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 5: USER PREFERENCES (Optional)
    # ═══════════════════════════════════════════════════════════════
    
    print("\nPhase 5: Setting user preferences...")
    
    # User 42 prefers GPT-3.5 for Agent 1 (overrides agent default)
    integration.configure_user_specific_agent_provider_model(
        workspace_id=workspace_id,
        user_id=42,
        agent_id=1,
        provider_name="azure",
        deployment_name="gpt-35-turbo"
    )
    
    print("✓ User preferences configured")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 6: LLM USAGE - Simple Generation
    # ═══════════════════════════════════════════════════════════════
    
    print("\nPhase 6: Using LLM for generation...")
    
    helper = get_llm_helper(database_url)
    
    # Simple text generation
    response1 = helper.get_llm_response(
        workspace_id=workspace_id,
        agent_id=1,
        prompt="What are the key principles of agile development?",
        user_id=42
    )
    
    print(f"\n📝 Response 1:\n{response1[:200]}...")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 7: LLM USAGE - Context-Aware
    # ═══════════════════════════════════════════════════════════════
    
    print("\nPhase 7: Using LLM with context...")
    
    response2 = helper.get_llm_response_with_context(
        workspace_id=workspace_id,
        agent_id=1,
        sys_prompt="You are a product management expert",
        user_input="How should I prioritize features in my backlog?",
        history=[
            {"role": "user", "content": "I'm managing a SaaS product"},
            {"role": "assistant", "content": "Great! I can help with that."}
        ],
        user_id=42
    )
    
    print(f"\n📝 Response 2:\n{response2[:200]}...")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 8: LANGCHAIN INTEGRATION
    # ═══════════════════════════════════════════════════════════════
    
    print("\nPhase 8: Using with LangChain...")
    
    llm = helper.get_router_llm(
        workspace_id=workspace_id,
        agent_id=1,
        user_id=42
    )
    
    # Use in LangChain chain
    from langchain_core.prompts import ChatPromptTemplate
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a concise assistant"),
        ("user", "{input}")
    ])
    
    chain = prompt | llm
    response3 = chain.invoke({"input": "Define 'technical debt' in one sentence"})
    
    print(f"\n📝 Response 3:\n{response3.content}")
    
    # ═══════════════════════════════════════════════════════════════
    # VERIFICATION
    # ═══════════════════════════════════════════════════════════════
    
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)
    
    # Check model resolution
    model_info = helper.get_current_model_info(
        workspace_id=workspace_id,
        agent_id=1,
        user_id=42
    )
    
    print(f"\nResolved model for user 42, agent 1:")
    print(f"  Provider: {model_info['provider_name']}")
    print(f"  Model: {model_info['deployment_name']}")
    print(f"  TrustAI Key: {model_info['trustai_model_key']}")
    
    print("\n✓ Integration complete!")

# Run the example
if __name__ == "__main__":
    asyncio.run(complete_integration_example())
```

---

## Summary

### Key Takeaways

1. **Three-Phase Integration**
   - **Setup**: Database + Provider Models + Workspace Registration
   - **Configuration**: Agent defaults + User preferences
   - **Execution**: Model resolution + TrustAI API calls

2. **Flexible Model Resolution**
   - User preference (highest priority)
   - Agent default (mid priority)
   - System default (fallback)

3. **Multiple Usage Patterns**
   - Direct provider access
   - Simple helper methods
   - LangChain compatibility
   - LangGraph agent support
   - Structured outputs

4. **Production-Ready Features**
   - Connection pooling
   - Automatic table creation
   - Comprehensive error handling
   - Logging and monitoring
   - Tool calling support

### Quick Reference

| Task | Entry Point |
|------|-------------|
| Initialize | `TrustAIDatabaseManager(db_url).initialize_tables()` |
| Register | `integration.register_workspace(ws_id, config)` |
| Configure Model | `integration.configure_agent_provider_model(...)` |
| Simple LLM Call | `helper.get_llm_response(ws_id, agent_id, prompt)` |
| LangChain LLM | `helper.get_router_llm(ws_id, agent_id, user_id)` |
| Check Model | `helper.get_current_model_info(ws_id, agent_id)` |

---

**Document Version**: 1.0  
**Last Updated**: 2026-07-17  
**Integration Package**: common_adapters.trustai v1.0.0
