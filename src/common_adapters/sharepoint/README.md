# SharePoint Integration

Reusable SharePoint adapter for multi-agent systems. Handles auth against
Microsoft Graph, per-user client caching, file discovery, metadata-filtered
extraction, and agent tool registration.

---

## 1. What's in this package

| File | Purpose |
| --- | --- |
| `client.py` | `SharePointClient` — MSAL auth + site-id resolution against Microsoft Graph. |
| `service.py` | `SharePointService` — list / download / **extract with metadata filter** / OCR via Azure Document Intelligence. |
| `sharepoint_client_manager.py` | `SharePointClientManagerAsync` — async, TTL-cached, per-user client factory. |
| `sharepoint_connection.py` | `test_sharepoint_connection`, `toggle_sharepoint_connection` — UI/API hooks for "Test" and "Enable/Disable" buttons. |
| `sharepoint_update_config.py` | `sharepoint_update_config` — sets `sharepoint_active` flag from a config dict. |

---

## 2. Required configuration

Each user's config (stored via your `config_manager`) must include:

```json
{
  "sharepoint_active": true,
  "tenant_id": "...",
  "client_id": "...",
  "client_secret": "...",
  "site_hostname": "contoso.sharepoint.com",
  "site_path": "/sites/MySite"
}
```

Environment variables (only needed if you call `extract_data` / OCR):

```
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<your-di>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<key>
```

---

## 3. The metadata filter

`SharePointService.extract_data(folder_path, metadata_map)` walks the folder
tree and only OCRs files that match `metadata_map`. Pass `None` (or omit) to
process every file.

| Key | Type | Behavior |
| --- | --- | --- |
| `file_types` | `list[str]` | Extensions, dot optional: `["pdf", ".docx"]`. |
| `name_contains` | `str` | Case-insensitive substring match on file name. |
| `min_size` / `max_size` | `int` (bytes) | Inclusive bounds. `0` is honored. |
| `created_after` / `created_before` | `datetime` or ISO 8601 string | Filters on `createdDateTime`. |
| `modified_after` / `modified_before` | `datetime` or ISO 8601 string | Filters on `lastModifiedDateTime`. |

**Example — only PDFs modified in the last 30 days, between 10 KB and 5 MB:**

```python
from datetime import datetime, timedelta, timezone
from common_adapters.sharepoint import SharePointClient, SharePointService

client = SharePointClient(tenant_id, client_id, client_secret, site_hostname, site_path)
service = SharePointService(client)

metadata_map = {
    "file_types": ["pdf"],
    "min_size": 10_000,
    "max_size": 5_000_000,
    "modified_after": datetime.now(timezone.utc) - timedelta(days=30),
}

docs = service.extract_data(folder_path="Shared Documents/Invoices", metadata_map=metadata_map)
for d in docs:
    print(d["name"], d["metadata"]["modified_at"], len(d["text"] or ""))
```

Each returned document looks like:

```python
{
  "id": "<graph item id>",
  "name": "invoice_2025_03.pdf",
  "content": "...OCR text...",
  "text":    "...OCR text...",
  "metadata": {
    "source": "sharepoint://contoso.sharepoint.com/sites/MySite/invoice_2025_03.pdf",
    "file_type": ".pdf",
    "size": 184221,
    "created_at": "2025-03-04T10:11:00Z",
    "modified_at": "2025-03-12T09:00:00Z",
    "url": "https://contoso.sharepoint.com/.../invoice_2025_03.pdf",
    "sharepoint_id": "<graph item id>",
    "mime_type": "application/pdf"
  }
}
```

---

## 4. Test and toggle flows (UI/API surface)

### Test connection

```python
from common_adapters.sharepoint import (
    SharePointClient, test_sharepoint_connection,
)

result = await test_sharepoint_connection(
    workspace_id="ws_123",
    user_id="user_42",
    data={
        "tenant_id": "...",
        "client_id": "...",
        "client_secret": "...",
        "site_hostname": "contoso.sharepoint.com",
        "site_path": "/sites/MySite",
    },
    sharepoint_client_class=SharePointClient,
    user_config_manager=user_config_manager,
)
# -> {"status": "success", "message": "...", "exists": True/False}
```

### Toggle on/off

```python
from common_adapters.sharepoint import (
    SharePointClientManagerAsync, toggle_sharepoint_connection,
)

sp_manager = SharePointClientManagerAsync(config_manager=user_config_manager)

await toggle_sharepoint_connection(
    workspace_id="ws_123",
    user_id="user_42",
    enable=False,                          # or True
    sharepoint_client_manager=sp_manager,
    user_config_manager=user_config_manager,
)
```

Disabling clears the user's cached client so the next call re-authenticates.

---

## 5. End-to-end flow

```
config_manager ── reads user creds ──▶ SharePointClientManagerAsync
                                              │  (TTL cache, per user)
                                              ▼
                                       SharePointClient ── MSAL ──▶ Microsoft Graph
                                              │
                                              ▼
                                       SharePointService
                                       (list / download / extract_data + metadata_map)
```

---

## 6. Notes & gotchas

- `site_path` must start with `/` (e.g. `/sites/MySite`). Graph rejects it otherwise.
- The metadata filter operates on file metadata returned by Graph — it does **not** filter on document contents. Filter first, then OCR.
- `extract_data` uses Azure Document Intelligence (`prebuilt-read`). Files for which OCR fails still appear in the result with `text=None`; check before indexing.
- `SharePointClientManagerAsync` caches clients for 15 minutes per `(user_id, tenant_id, site_hostname)`. `toggle_sharepoint_connection(enable=False)` evicts the entry.
- Tool calls run inside the agent process; make sure `AZURE_DOCUMENT_INTELLIGENCE_*` env vars are set wherever the agent runs.
