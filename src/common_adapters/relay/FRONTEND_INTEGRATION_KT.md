# Unified Relay Frontend Integration KT

## Overview

The unified relay service already supports frontend WebSocket subscriptions, session scoping, and multi-tab broadcasting.

Frontend clients connect directly using:

```text
wss://forgex-unified-relay-dcfuevd7dgb8fzep.eastus2-01.azurewebsites.net/ws
```

The relay internally routes connections using:

```text
agent -> session/channel -> tab_id -> websocket
```

No backend changes are currently required for frontend-controlled broadcast behavior.

---

## WebSocket URL Format

```text
wss://<relay-host>/ws?agent=<agent>&channel=<conversation_id>
```

Example:

```text
wss://forgex-unified-relay-dcfuevd7dgb8fzep.eastus2-01.azurewebsites.net/ws?agent=po&channel=20260817_084607_486f14e7
```

---

## Supported Query Parameters

### agent

Supported values:

- ba
- po
- qe
- arch
- devagent
- kb
- all

`all` subscribes to all agent streams for the same session/channel.

---

### channel

Logical conversation/session identifier.

All connections using the same:

- agent
- channel

receive the same updates.

This is the main broadcast scope.

---

### tab_id (Optional)

Unique browser-tab identifier.

If omitted, relay auto-generates one.

Useful for frontend analytics/debugging, but broadcast behavior is primarily controlled by the `channel` value.

---

## Existing Broadcast Behavior

The relay already supports all required frontend modes.

### Shared Broadcast Across Tabs

Use the same `channel` in multiple tabs.

Example:

```text
Tab A:
wss://host/ws?agent=po&channel=conv_123&tab_id=tab_a

Tab B:
wss://host/ws?agent=po&channel=conv_123&tab_id=tab_b
```

Result:

- both tabs receive identical updates
- messages are fanned out automatically by relay

---

### Isolated Per-Tab Sessions

Generate a unique `channel` per tab.

Example:

```text
Tab A:
wss://host/ws?agent=po&channel=conv_123_tab_a

Tab B:
wss://host/ws?agent=po&channel=conv_123_tab_b
```

Result:

- no cross-tab updates
- each tab receives isolated streams

---

### Listen To All Agents

Example:

```text
wss://host/ws?agent=all&channel=conv_123
```

Result:

- frontend receives updates from all configured agent streams

---

## Recommended Frontend Toggle Design

Frontend can fully control broadcast behavior without backend changes.

### Broadcast Toggle ON

Reuse the same conversation ID as channel.

```ts
const channel = conversationId;
```

All tabs receive the same updates.

---

### Broadcast Toggle OFF

Generate a unique channel per tab.

```ts
const channel = `${conversationId}_${tabId}`;
```

or:

```ts
const channel = crypto.randomUUID();
```

Tabs become isolated subscribers.

---

## Recommended Frontend Helper

```ts
type RelayOptions = {
  agent: "ba" | "po" | "qe" | "arch" | "devagent" | "kb" | "all";
  conversationId: string;
  broadcastAcrossTabs?: boolean;
};

export function createRelaySocket(options: RelayOptions) {
  let tabId = sessionStorage.getItem("relay_tab_id");

  if (!tabId) {
    tabId = crypto.randomUUID();
    sessionStorage.setItem("relay_tab_id", tabId);
  }

  const channel = options.broadcastAcrossTabs
    ? options.conversationId
    : `${options.conversationId}_${tabId}`;

  const url = new URL(
    "wss://forgex-unified-relay-dcfuevd7dgb8fzep.eastus2-01.azurewebsites.net/ws"
  );

  url.searchParams.set("agent", options.agent);
  url.searchParams.set("channel", channel);
  url.searchParams.set("tab_id", tabId);

  return new WebSocket(url.toString());
}
```

---

## Heartbeat Support

Frontend may send:

```json
{
  "type": "ping"
}
```

Relay responds with:

```json
{
  "type": "pong",
  "ts": 1755580000
}
```

Useful for reconnect handling and connection health monitoring.

---

## Relevant Backend Implementation

Primary implementation file:

```text
forgexpackages/src/common_adapters/relay/unified_relay.py
```

Notification abstraction layer:

```text
forgexpackages/src/common_adapters/notifications/
```

Key methods:

- `UnifiedConnectionManager.connect()`
- `UnifiedConnectionManager.send_to_agent_session()`
- `UnifiedConnectionManager.broadcast_to_agent()`
- `websocket_endpoint()`
- `ConnectionManager.send_to_tab()`
- `ConnectionManager.send_to_session()`

Broadcast configuration:

```python
class BroadcastMode(str, Enum):
    TAB = "tab"
    SESSION = "session"
```

Mapping to frontend behavior:

| Backend Mode | Frontend Behavior |
| --- | --- |
| `BroadcastMode.TAB` | Use unique `channel` per tab |
| `BroadcastMode.SESSION` | Reuse same `channel` across tabs |

Important implementation detail:

- `send_to_tab()` targets only one browser tab
- `send_to_session()` fans out to all tabs in the same session
- elicitation requests are intentionally tab-scoped to avoid duplicate prompts

Current implementation already supports:

- multiple tabs per session
- isolated sessions
- agent-level subscriptions
- all-agent subscriptions
- automatic fanout

No relay code changes are required for frontend integration.
