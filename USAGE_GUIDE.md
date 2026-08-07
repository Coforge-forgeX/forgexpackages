# common-adapters Usage Guide

## Overview

`common-adapters` is a shared Python package providing cloud-agnostic services for forgeX agents. The package follows a **pure service** design: agents pass explicit configuration, and the package provides services without reading environment variables.

**Design Principle**: *"Agent decides what it needs, and common package will service whatever agent needs"*

## Installation

### Development (editable install)
```bash
pip install -e D:\forgex-rearch\forgexpackages
```

### Production
```bash
pip install git+https://github.com/Coforge-forgeX/forgexpackages.git@main
```

## Azure Functions Setup

For Azure Functions, add `PYTHONPATH` to `local.settings.json`:

```json
{
  "Values": {
    "PYTHONPATH": "D:\\forgex-rearch\\forgexpackages\\src;D:\\venv-arch\\ba\\Lib\\site-packages;D:\\forgex-rearch\\BusinessAnalyst\\src"
  }
}
```

---

## Modules

### 1. Cloud Provider (`common_adapters.cloud`)

#### CloudProvider Enum
```python
from common_adapters.cloud import CloudProvider

# Parse from string (case-insensitive)
provider = CloudProvider.parse("azure")  # CloudProvider.AZURE
provider = CloudProvider.parse("aws")    # CloudProvider.AWS
provider = CloudProvider.parse("local")  # CloudProvider.LOCAL
```

#### Secret Providers
```python
from common_adapters.cloud import EnvSecretProvider, AzureKeyVaultSecretProvider

# Environment-based secrets
env_secrets = EnvSecretProvider(env_getter=os.getenv)
value = env_secrets.get_secret("MY_SECRET_KEY")

# Azure Key Vault secrets
kv_secrets = AzureKeyVaultSecretProvider(keyvault_url="https://my-vault.vault.azure.net")
value = await kv_secrets.get_secret("my-secret")
```

#### Object Storage
```python
from common_adapters.cloud import AzureBlobStorageService, S3StorageService

# Azure Blob Storage
azure_storage = AzureBlobStorageService(
    connection_string="DefaultEndpointsProtocol=https;AccountName=..."
)
content = await azure_storage.download_blob("container-name", "blob-path")
await azure_storage.upload_blob("container-name", "blob-path", content)

# AWS S3
s3_storage = S3StorageService(region_name="us-east-1")
content = await s3_storage.download_blob("bucket-name", "key")
await s3_storage.upload_blob("bucket-name", "key", content)
```

---

### 2. Progress Reporting (`common_adapters.progress`)

#### Create Publishers
```python
from common_adapters.progress import (
    create_null_publisher,
    create_log_publisher,
    create_local_relay_publisher,
    create_azure_servicebus_publisher,
)

# No-op publisher (for testing)
publisher = create_null_publisher()

# Logging publisher
publisher = create_log_publisher()

# Local HTTP relay (for local dev)
publisher = create_local_relay_publisher(url="http://127.0.0.1:8090/publish")

# Azure Service Bus (topic)
publisher = create_azure_servicebus_publisher(
    connection_string="Endpoint=sb://...",
    entity_name="ba-dev",
    entity_type="topic"
)

# Azure Service Bus (queue)
publisher = create_azure_servicebus_publisher(
    connection_string="Endpoint=sb://...",
    entity_name="my-queue",
    entity_type="queue"
)
```

#### Create Progress Reporter
```python
from common_adapters.progress import create_progress_reporter

reporter = create_progress_reporter(
    publisher=publisher,
    workspace_id=1003,
    agent_id=7,
    job_id="job-123",
    heartbeat_interval_s=2.0
)

# Report progress
await reporter.report("Processing started", percentage=10)
await reporter.report("Analyzing data", percentage=50)
await reporter.complete("Done!")
await reporter.fail("Something went wrong")
```

---

### 3. MCP Client (`common_adapters.mcp`)

#### MCPSettings Configuration
```python
from common_adapters.mcp import MCPSettings

settings = MCPSettings(
    mcp_jira_url="https://jira-server/mcp",
    mcp_ado_url="https://ado-server/mcp",
    mcp_timeout_s=30,
    mcp_init_timeout_s=10,
    mcp_auth_token="bearer-token",
    mcp_subscription_key="subscription-key",
)
```

#### MCP App Client
```python
from common_adapters.mcp import MCPAppClient, MCPSettings

settings = MCPSettings(
    mcp_jira_url="https://jira.example.com/mcp",
    mcp_timeout_s=30,
)

client = MCPAppClient(
    settings=settings,
    cache_ttl_s=180,
)

# Call a tool
result = await client.call_tool("jira_search", {"query": "project = BA"})

# List available tools
tools = await client.list_tools()
```

---

### 4. Notifications (`common_adapters.notifications`)

#### WebSocket Connection Manager
```python
from common_adapters.notifications import ConnectionManager, BroadcastMode

manager = ConnectionManager(
    broadcast_mode=BroadcastMode.SESSION,
    max_queue_size=200,
    ping_interval_s=25,
    idle_timeout_s=180,
)

# Accept connection
await manager.connect(websocket, session_id="session-123")

# Send message to session
await manager.send_to_session("session-123", {"type": "progress", "data": {...}})

# Broadcast to all
await manager.broadcast({"type": "system", "message": "Server restarting"})

# Disconnect
await manager.disconnect(websocket)
```

---

## Migration Guide

### Old API (env-based) → New API (explicit)

#### Cloud Provider
```python
# OLD (removed)
from common_adapters.cloud import resolve_cloud_provider
provider = resolve_cloud_provider()  # Read CLOUD_PROVIDER env

# NEW
from common_adapters.cloud import CloudProvider
provider = CloudProvider.parse(os.getenv("CLOUD_PROVIDER", "local"))
```

#### Secret Provider
```python
# OLD (removed)
from common_adapters.cloud import get_secret_provider
provider = get_secret_provider()  # Auto-detect from env

# NEW
from common_adapters.cloud import EnvSecretProvider, AzureKeyVaultSecretProvider

secret_provider_type = os.getenv("SECRET_PROVIDER", "env")
if secret_provider_type == "env":
    provider = EnvSecretProvider(env_getter=os.getenv)
elif secret_provider_type == "azure_keyvault":
    provider = AzureKeyVaultSecretProvider(keyvault_url=os.getenv("KEYVAULT_URL"))
```

#### Object Storage
```python
# OLD (removed)
from common_adapters.cloud import get_object_storage_service
storage = get_object_storage_service()  # Auto-detect from env

# NEW
from common_adapters.cloud import AzureBlobStorageService, S3StorageService

storage_type = os.getenv("OBJECT_STORAGE_PROVIDER", "azure_blob")
if storage_type == "azure_blob":
    storage = AzureBlobStorageService(
        connection_string=os.getenv("AZURE_BLOB_STORAGE_CONNECTION_STRING")
    )
elif storage_type == "s3":
    storage = S3StorageService(region_name=os.getenv("AWS_REGION", "us-east-1"))
```

#### Progress Publisher
```python
# OLD (removed)
from common_adapters.progress import get_progress_publisher
publisher = get_progress_publisher()  # Auto-detect from env

# NEW
from common_adapters.progress import (
    create_null_publisher,
    create_log_publisher,
    create_local_relay_publisher,
    create_azure_servicebus_publisher,
)

backend = os.getenv("PROGRESS_BACKEND", "log")
if backend == "null":
    publisher = create_null_publisher()
elif backend == "log":
    publisher = create_log_publisher()
elif backend == "local_relay":
    publisher = create_local_relay_publisher(url=os.getenv("PROGRESS_LOCAL_RELAY_URL"))
elif backend == "azure_service_bus":
    publisher = create_azure_servicebus_publisher(
        connection_string=os.getenv("EVENT_BUS_CONNECTION_STRING"),
        entity_name=os.getenv("PROGRESS_TOPIC") or os.getenv("PROGRESS_QUEUE"),
        entity_type="topic" if os.getenv("PROGRESS_TOPIC") else "queue"
    )
```

#### MCP Settings
```python
# OLD (removed)
from common_adapters.mcp import mcp_settings  # Global singleton

# NEW
from common_adapters.mcp import MCPSettings

settings = MCPSettings(
    mcp_jira_url=os.getenv("MCP_JIRA_URL"),
    mcp_ado_url=os.getenv("MCP_ADO_URL"),
    mcp_timeout_s=int(os.getenv("MCP_TIMEOUT_S", "30")),
    mcp_init_timeout_s=int(os.getenv("MCP_INIT_TIMEOUT_S", "10")),
    mcp_auth_token=os.getenv("MCP_AUTH_TOKEN"),
    mcp_subscription_key=os.getenv("MCP_SUBSCRIPTION_KEY"),
)
```

---

## Example: Agent Bootstrap

```python
import os
from common_adapters.cloud import (
    CloudProvider,
    EnvSecretProvider,
    AzureBlobStorageService,
)
from common_adapters.progress import (
    create_azure_servicebus_publisher,
    create_progress_reporter,
)
from common_adapters.mcp import MCPSettings, MCPAppClient


def bootstrap_agent():
    """Initialize all services from environment variables."""
    
    # Cloud provider
    cloud = CloudProvider.parse(os.getenv("CLOUD_PROVIDER", "local"))
    
    # Secrets
    secrets = EnvSecretProvider(env_getter=os.getenv)
    
    # Storage
    storage = AzureBlobStorageService(
        connection_string=os.getenv("AZURE_BLOB_STORAGE_CONNECTION_STRING")
    )
    
    # Progress publisher
    publisher = create_azure_servicebus_publisher(
        connection_string=os.getenv("EVENT_BUS_CONNECTION_STRING"),
        entity_name=os.getenv("PROGRESS_TOPIC", "ba-dev"),
        entity_type="topic"
    )
    
    # MCP client
    mcp_settings = MCPSettings(
        mcp_jira_url=os.getenv("MCP_JIRA_URL"),
        mcp_timeout_s=int(os.getenv("MCP_TIMEOUT_S", "30")),
    )
    mcp_client = MCPAppClient(settings=mcp_settings, cache_ttl_s=180)
    
    return {
        "cloud": cloud,
        "secrets": secrets,
        "storage": storage,
        "publisher": publisher,
        "mcp_client": mcp_client,
    }
```

---

## Version

Current version: **3.1.0**

## Repository

https://github.com/Coforge-forgeX/forgexpackages
