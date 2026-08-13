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
| **Runtime** | Docker Container |
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

### Container Startup

The relay is deployed directly from the repository `Dockerfile`.

The container startup command is:

```dockerfile
CMD ["sh","-c","gunicorn -k uvicorn.workers.UvicornWorker common_adapters.relay.unified_relay:app --bind 0.0.0.0:${PORT:-8000} --timeout 120 --workers 1"]
```

Important:
- Azure App Service injects a dynamic `PORT` environment variable
- The container must bind to `${PORT}` or health checks fail with `503 Service Unavailable`
- Do not hardcode port `8000` in Azure container deployments

---

## Application Settings (Environment Variables)

### Required Settings

| Name | Value | Description |
|------|-------|-------------|
| `SERVICE_BUS_CONNECTION_STRING` | `Endpoint=sb://forgexsb.servicebus.windows.net/;...` | Service Bus connection string |
| `RELAY_TOPICS` | `ba-dev,po-dev,arch-dev` | Comma-separated list of topics to subscribe to |
| `RELAY_SUBSCRIPTION_PREFIX` | `unified-relay` | Prefix for subscription names |
| `PYTHONPATH` | Not required | Package is installed inside the container |

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

## Docker Deployment

The relay should be deployed using the repository `Dockerfile`.

### Build Container

```bash
docker build -t forgex-unified-relay .
```

### Run Locally

```bash
docker run -p 8000:8000 \
  -e SERVICE_BUS_CONNECTION_STRING="<connection-string>" \
  -e RELAY_TOPICS="ba-dev,po-dev" \
  -e RELAY_SUBSCRIPTION_PREFIX="unified-relay" \
  forgex-unified-relay
```

### Azure Container Registry (Optional)

```bash
az acr build \
  --registry <acr-name> \
  --image forgex-unified-relay:latest \
  .
```

### Configure Azure Web App for Containers

```bash
az webapp create \
    --resource-group <your-rg> \
    --plan <your-plan> \
    --name forgex-unified-relay \
    --deployment-container-image-name <acr-name>.azurecr.io/forgex-unified-relay:latest
```

### Configure Container Settings

```bash
az webapp config container set \
    --resource-group <your-rg> \
    --name forgex-unified-relay \
    --container-image-name <acr-name>.azurecr.io/forgex-unified-relay:latest
```

Do not configure a separate Startup Command in Azure when using the Docker container.

---

## WebSocket Connection
#### wss://forgex-unified-relay-dcfuevd7dgb8fzep.eastus2-01.azurewebsites.net/ws?agent=ba&channel=test-conv-001
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
- Verify the Docker image builds successfully
- Verify `pip install .` succeeds during image build
- Verify the container starts locally before Azure deployment

---

## Azure CLI Quick Reference

```bash
# Create Web App for Containers
az webapp create \
    --resource-group <your-rg> \
    --plan <your-plan> \
    --name forgex-unified-relay \
    --deployment-container-image-name <acr-name>.azurecr.io/forgex-unified-relay:latest

# Enable WebSockets + Always On
az webapp config set \
    --resource-group <your-rg> \
    --name forgex-unified-relay \
    --web-sockets-enabled true \
    --always-on true

# Set App Settings
az webapp config appsettings set \
    --resource-group <your-rg> \
    --name forgex-unified-relay \
    --settings \
        SERVICE_BUS_CONNECTION_STRING="<connection-string>" \
        RELAY_TOPICS="ba-dev,po-dev,arch-dev" \
        RELAY_SUBSCRIPTION_PREFIX="unified-relay"
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
