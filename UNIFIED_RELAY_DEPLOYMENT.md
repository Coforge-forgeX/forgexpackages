# Unified WebSocket Relay Deployment Guide

A **single, centralized** relay service that subscribes to **multiple** Azure Service Bus topics and routes messages dynamically to WebSocket clients based on agent type.

---

## Why Unified Relay?

| Approach | Web Apps | Cost | Maintenance |
|----------|----------|------|-------------|
| **Per-Agent Relay** | 3+ (BA, PO, Arch...) | Higher | Multiple deployments |
| **Unified Relay** | 1 | **Lower** | Single deployment |

The unified relay subscribes to ALL agent topics and routes messages to the correct clients based on the `agent` parameter in the WebSocket connection.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Azure Service Bus                            │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐          │
│  │ ba-dev  │   │ po-dev  │   │arch-dev │   │ qa-dev  │          │
│  └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘          │
└───────┼─────────────┼─────────────┼─────────────┼───────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │   Unified Relay        │
                │   (Single Web App)     │
                │                        │
                │  ┌──────────────────┐  │
                │  │ Topic Consumers  │  │
                │  │ (one per topic)  │  │
                │  └────────┬─────────┘  │
                │           │            │
                │  ┌────────▼─────────┐  │
                │  │ ConnectionManager│  │
                │  │ (routes by agent │  │
                │  │  + conversation) │  │
                │  └────────┬─────────┘  │
                └───────────┼────────────┘
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
       ▼                    ▼                    ▼
┌────────────┐       ┌────────────┐       ┌────────────┐
│ BA Client  │       │ PO Client  │       │Arch Client │
│ (Frontend) │       │ (Frontend) │       │ (Frontend) │
└────────────┘       └────────────┘       └────────────┘
```

---

## Azure Web App Requirements

### Resource Specifications

| Setting | Value |
|---------|-------|
| **Name** | `forgex-unified-relay` |
| **Runtime** | Python 3.12 |
| **Operating System** | Linux |
| **SKU/Plan** | B1 or S1 (must support WebSockets) |
| **Region** | Same as Service Bus (e.g., East US 2) |

### Required Configuration

Navigate to **Configuration → General settings**:

| Setting | Value | Required |
|---------|-------|----------|
| **WebSockets** | **ON** | ✅ Critical |
| **Always On** | **ON** | ✅ Critical |
| **HTTP Version** | 1.1 | Recommended |

### Startup Command

```bash
gunicorn -k uvicorn.workers.UvicornWorker common_adapters.relay.unified_relay:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1
```

---

## Application Settings (Environment Variables)

### Required Settings

| Name | Value | Description |
|------|-------|-------------|
| `SERVICE_BUS_CONNECTION_STRING` | `Endpoint=sb://forgexsb.servicebus.windows.net/;...` | Service Bus connection string |
| `RELAY_TOPICS` | `ba-dev,po-dev,arch-dev` | Comma-separated list of topics to subscribe to |
| `RELAY_SUBSCRIPTION_PREFIX` | `unified-relay` | Prefix for subscription names |
| `PYTHONPATH` | `/home/site/wwwroot/src` | Required for imports |

### Optional Settings

| Name | Default | Description |
|------|---------|-------------|
| `WS_MAX_QUEUE` | `200` | Max WebSocket message queue |
| `WS_PING_INTERVAL_S` | `25` | Ping interval for keepalive |
| `WS_IDLE_TIMEOUT_S` | `180` | Idle timeout |

### Key Vault Reference (Recommended)

```
@Microsoft.KeyVault(SecretUri=https://your-keyvault.vault.azure.net/secrets/ServiceBusConnectionString/)
```

---

## Service Bus Setup

The relay will auto-create subscriptions with names like:
- `unified-relay-ba-dev`
- `unified-relay-po-dev`
- `unified-relay-arch-dev`

### Pre-create Subscriptions (Optional)

```bash
# For each topic
for topic in ba-dev po-dev arch-dev; do
    az servicebus topic subscription create \
        --resource-group <your-rg> \
        --namespace-name forgexsb \
        --topic-name $topic \
        --name unified-relay-$topic
done
```

---

## Code Location

The unified relay is in `forgexpackages`:

```
forgexpackages/
└── src/
    └── common_adapters/
        └── relay/
            ├── __init__.py
            └── unified_relay.py   ← Main entry point
```

---

## Deployment

### Option 1: Deploy forgexpackages as a Package

The unified relay is part of `common_adapters`. Deploy it by installing the package:

**requirements.txt for the Web App:**
```txt
common-adapters @ git+https://github.com/Coforge-forgeX/forgexpackages.git@main
fastapi
uvicorn
gunicorn
azure-servicebus
```

### Option 2: Copy Files Directly

```powershell
# Create deployment package
$deployDir = "unified-relay-deploy"
New-Item -ItemType Directory -Force -Path $deployDir/src/common_adapters/relay

# Copy relay module
Copy-Item forgexpackages/src/common_adapters/relay/*.py $deployDir/src/common_adapters/relay/

# Create __init__.py files
"" | Out-File $deployDir/src/__init__.py
"" | Out-File $deployDir/src/common_adapters/__init__.py

# Create requirements.txt
@"
fastapi>=0.100.0
uvicorn>=0.22.0
gunicorn>=21.0.0
azure-servicebus>=7.11.0
"@ | Out-File $deployDir/requirements.txt

# Create startup script
@"
#!/bin/bash
cd /home/site/wwwroot
gunicorn -k uvicorn.workers.UvicornWorker common_adapters.relay.unified_relay:app --bind 0.0.0.0:`$PORT --timeout 120 --workers 1
"@ | Out-File $deployDir/startup.sh

# ZIP and deploy
Compress-Archive -Path "$deployDir/*" -DestinationPath unified-relay.zip -Force
```

Deploy:
```bash
az webapp deployment source config-zip \
    --resource-group <your-rg> \
    --name forgex-unified-relay \
    --src unified-relay.zip
```

---

## WebSocket Connection

### Frontend Usage

```javascript
// Connect for BA agent messages
const ws = new WebSocket('wss://forgex-unified-relay.azurewebsites.net/ws?agent=ba&channel=' + conversationId);

// Connect for PO agent messages
const ws = new WebSocket('wss://forgex-unified-relay.azurewebsites.net/ws?agent=po&channel=' + conversationId);

// Connect for ALL agent messages (useful for debugging)
const ws = new WebSocket('wss://forgex-unified-relay.azurewebsites.net/ws?agent=all&channel=' + conversationId);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`[${data.agent}] ${data.event.status}: ${data.event.message}`);
};
```

### Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `agent` | No (default: `all`) | Agent to listen to: `ba`, `po`, `architect`, `qa`, `all` |
| `channel` | Yes | Conversation ID for routing |
| `session_id` | No | Alias for `channel` |
| `tab_id` | No | Browser tab ID (auto-generated if missing) |

### Message Format

Messages received on WebSocket:
```json
{
    "type": "progress",
    "agent": "ba",
    "topic": "ba-dev",
    "channel": "conv_123",
    "event": {
        "conversation_id": "conv_123",
        "job_id": "job_456",
        "status": "in_progress",
        "operation": "analyze",
        "message": "Analyzing requirements..."
    }
}
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info and usage |
| `/health` | GET | Health check with stats |
| `/ws` | WebSocket | Message subscription |

### Health Check Response

```json
{
    "status": "ok",
    "service": "unified-servicebus-relay",
    "topics": ["ba-dev", "po-dev", "arch-dev"],
    "subscription_prefix": "unified-relay",
    "stats": {
        "total_clients": 5,
        "total_sessions": 3,
        "by_agent": {
            "ba": {"sessions": 2, "clients": 3},
            "po": {"sessions": 1, "clients": 2}
        }
    }
}
```

---

## Adding New Agents

To add a new agent (e.g., QA agent):

1. **Create the Service Bus topic:**
   ```bash
   az servicebus topic create \
       --resource-group <your-rg> \
       --namespace-name forgexsb \
       --name qa-dev
   ```

2. **Update the `RELAY_TOPICS` setting:**
   ```
   RELAY_TOPICS=ba-dev,po-dev,arch-dev,qa-dev
   ```

3. **Restart the Web App** (or it will pick up on next deployment)

The relay auto-creates the subscription and starts consuming.

---

## Verification

### 1. Health Check

```bash
curl https://forgex-unified-relay.azurewebsites.net/health
```

### 2. Test WebSocket

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c "wss://forgex-unified-relay.azurewebsites.net/ws?agent=ba&channel=test-123"
```

### 3. View Logs

```bash
az webapp log tail --resource-group <your-rg> --name forgex-unified-relay
```

---

## Troubleshooting

### No Messages Received
- Check `RELAY_TOPICS` includes the correct topics
- Verify subscriptions were created (check Service Bus in Azure Portal)
- Ensure `SERVICE_BUS_CONNECTION_STRING` has Listen permissions

### WebSocket Connection Fails
- Verify **WebSockets** is enabled in Azure Portal
- Check **Always On** is enabled
- Verify CORS allows your frontend origin

### Import Errors
- Verify `PYTHONPATH=/home/site/wwwroot/src`
- Check all `__init__.py` files exist

---

## Azure CLI Quick Reference

```bash
# Create Web App
az webapp create \
    --resource-group <your-rg> \
    --plan <your-plan> \
    --name forgex-unified-relay \
    --runtime "PYTHON:3.12"

# Enable WebSockets + Always On
az webapp config set \
    --resource-group <your-rg> \
    --name forgex-unified-relay \
    --web-sockets-enabled true \
    --always-on true

# Set Startup Command
az webapp config set \
    --resource-group <your-rg> \
    --name forgex-unified-relay \
    --startup-file "gunicorn -k uvicorn.workers.UvicornWorker common_adapters.relay.unified_relay:app --bind 0.0.0.0:\$PORT --timeout 120 --workers 1"

# Set App Settings
az webapp config appsettings set \
    --resource-group <your-rg> \
    --name forgex-unified-relay \
    --settings \
        SERVICE_BUS_CONNECTION_STRING="<connection-string>" \
        RELAY_TOPICS="ba-dev,po-dev,arch-dev" \
        RELAY_SUBSCRIPTION_PREFIX="unified-relay" \
        PYTHONPATH="/home/site/wwwroot/src"
```

---

## Cost Comparison

| Setup | Monthly Cost (B1) | Notes |
|-------|-------------------|-------|
| 3 separate relays | ~$39/month | BA + PO + Architect |
| 1 unified relay | ~$13/month | **67% savings** |

---

## Summary

✅ **Single Web App** instead of multiple  
✅ **Subscribes to all topics** dynamically  
✅ **Routes by agent + conversation** automatically  
✅ **Easy to add new agents** (just add topic to RELAY_TOPICS)  
✅ **Cost-efficient** (single deployment, shared resources)
