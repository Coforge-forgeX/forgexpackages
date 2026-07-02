## cancel_convesation

Process-local, best-effort cancellation for long-running agent/LLM requests.

This module exists to support a common UI workflow:

1. User sends a prompt that triggers a long LLM call (or a multi-step pipeline).
2. User clicks a Stop/Cancel button.
3. The running request should stop immediately and return a deterministic
   "Request cancelled." response.
4. The next prompt in the same conversation should behave normally.

The design deliberately avoids "sticky" cancellation across subsequent prompts
in the same conversation (conversation IDs are often reused).

### Orchestrator Integration (Workflow Execution)

This repo includes an orchestrator service (workflow execution) that calls other
agents (BA/Architect/PO/etc) via MCP. To support a Stop button that works during
orchestration, the orchestrator must do two things:

1. Cancel its own in-flight await (so the UI returns immediately).
1. Forward cancellation to the currently active agent (so the agent stops token
   spend / work).

The orchestrator integration implemented in `workflow_execution` follows these
semantics:

- STOP is **request-scoped**, not job-scoped: it cancels the current in-flight
  run only.
- STOP must **not** change the overall workflow/job lifecycle (do not set
  `is_active=False`, do not mark the job `completed`/`cancelled`).
- The orchestration layer should clear cancellation at the beginning of new runs
  when reusing the same `conversation_id` (to avoid TTL poisoning).

#### Orchestrator Tools

- `cancel_conversation`: Exposed from this package for local, process-level
  cancellation (same as standalone agents).
- `cancel_active_conversation` (orchestrator wrapper): Cancels locally using
  `cancel_conversation(...)` and then forwards cancellation to the active stage
  agent's `cancel_conversation` tool.

The wrapper is required because the shared `cancel_conversation(...)` is a
generic, process-local primitive; it does not know how to route to a specific
remote agent.

#### Forwarding Contract

Orchestrator forwards cancellation to the active agent by calling:

```python
client.session.call_tool(
    "cancel_conversation",
    arguments={"conversation_id": job_id, "reason": "user_requested"},
)
```

This requires every agent to:

1. Expose tool name `cancel_conversation`.
1. Register its in-flight asyncio task with `register_task(conversation_id=...)`
   during long-running operations.

#### TTL Poisoning and Repeated STOP

This module uses a short-lived cancellation flag (`_CANCEL_TTL_SECONDS`). When
the same `conversation_id` is reused across multiple prompts, a STOP can
"poison" the next prompt if it starts within the TTL window.

To avoid this in orchestrated workflows:

- Clear cancellation at the start of a new run:

```python
from common_adapters.cancel_convesation import clear_cancellation

clear_cancellation(conversation_id=conversation_id)
```

- Make STOP idempotent by clearing and then cancelling:

```python
clear_cancellation(conversation_id=conversation_id)
cancel_conversation(conversation_id=conversation_id)
```

### Core Concepts

Cancellation is implemented using two complementary mechanisms.

1. Task cancellation (immediate interruption)
The fastest way to stop an in-flight async operation is to cancel the asyncio
Task that is currently awaiting the provider call.

We support this by associating an asyncio Task with a cancellation key via
`register_task(...)`. When `cancel_conversation(...)` is called, we locate the
registered Task and call `task.cancel()`.

This is what makes "Stop" return immediately instead of waiting for the LLM to
finish.

2. Short-lived cancellation flag (race-safe pipeline stop)
Sometimes the user cancels before the running request reaches the point where it
can register its Task. To handle this, we set a short-lived in-memory flag and
expose it via `is_cancelled(...)`.

Callers that execute multi-step pipelines should check `is_cancelled(...)` at
safe boundaries (before/after heavy steps) to stop the pipeline early.

This flag is TTL-based and auto-clears quickly to avoid poisoning subsequent
requests.

### Cancellation Keys

All cancellation operations are keyed by either:

- `job_id` (preferred if available): key format `job:<job_id>`
- `conversation_id` (fallback): key format `conv:<conversation_id>`

The helper `_cancellation_key(job_id=..., conversation_id=...)` enforces this.

### Quick Start: `cancel_conversation`

`cancel_conversation` is a synchronous entrypoint designed to be exposed as a tool (for example, via an MCP server) so a UI can stop an in-flight request.

Import it directly from this module:

```python
from common_adapters.cancel_convesation import cancel_conversation
```

Minimal usage:

```python
# Cancel by job_id when available (preferred)
cancel_conversation(job_id="123")

# Or cancel by conversation_id when job_id is not available
cancel_conversation(conversation_id="conv-abc")
```

Key behavior:

1. If a running asyncio task was registered for the same key, it is cancelled immediately.
1. A short-lived in-memory cancellation flag is set for the same key so multi-step pipelines can stop at safe boundaries.
1. The flag auto-clears after a short TTL to avoid cancelling subsequent prompts in the same conversation.

### Agent Integration Examples

This module supports two complementary integration patterns.

#### 1) Expose `cancel_conversation` as a Tool

Expose `cancel_conversation` so the UI can call it when the user clicks Stop/Cancel.

Example (pattern used in existing servers):

```python
from common_adapters.cancel_convesation import cancel_conversation


def register_tools(mcp) -> None:
    # Exposes tool name `cancel_conversation`.
    mcp.tool()(cancel_conversation)
```

The tool returns a payload like:

```json
{
  "status": "success",
  "cancelled": true,
  "key": "job:123",
  "job_id": "123",
  "conversation_id": null,
  "workspace_id": null,
  "user_id": null,
  "reason": "user_requested"
}
```

#### 2) Make Your Agent Work Cancel-Safely

To ensure cancellation interrupts an in-flight provider call, register the currently running asyncio task using `register_task(...)` and always `unregister_task(...)` in a `finally` block.

Example wrapper around a long-running async operation (LLM call, retrieval step, multi-stage pipeline):

```python
import asyncio

from common_adapters.cancel_convesation import (
    CancelledError,
    is_cancelled,
    register_task,
    unregister_task,
)


async def run_agent_step(*, conversation_id: str, job_id: str | None = None) -> dict:
    task = asyncio.current_task()
    if task is None:
        # Very uncommon, but keeps typing and runtime behavior explicit.
        raise RuntimeError("No current asyncio task")

    register_task(conversation_id=conversation_id, job_id=job_id, task=task)
    try:
        # Optional: check for a cancel that arrived slightly before registration.
        if await is_cancelled(conversation_id=conversation_id, job_id=job_id):
            return {
                "status": "success",
                "role": "assistant",
                "content": "Request cancelled.",
                "cancelled": True,
            }

        # Your long-running work here.
        # Replace this with the actual model/provider call.
        result = await do_provider_call()
        return {"status": "success", "role": "assistant", "content": result}

    except asyncio.CancelledError:
        # Important: return deterministic cancellation output.
        return {
            "status": "success",
            "role": "assistant",
            "content": "Request cancelled.",
            "cancelled": True,
        }
    except CancelledError:
        # If you use token-based cancellation checks in other layers.
        return {
            "status": "success",
            "role": "assistant",
            "content": "Request cancelled.",
            "cancelled": True,
        }
    finally:
        unregister_task(conversation_id=conversation_id, job_id=job_id)
```

Multi-step pipelines should check `is_cancelled(...)` at safe boundaries:

```python
from common_adapters.cancel_convesation import is_cancelled


async def pipeline(*, conversation_id: str) -> dict:
    if await is_cancelled(conversation_id=conversation_id):
        return {"status": "success", "content": "Request cancelled.", "cancelled": True}

    step1 = await expensive_step_1()

    if await is_cancelled(conversation_id=conversation_id):
        return {"status": "success", "content": "Request cancelled.", "cancelled": True}

    step2 = await expensive_step_2(step1)
    return {"status": "success", "content": step2}
```

### Public API

These are the functions intended to be imported and used.

#### `cancel_conversation(...) -> dict`

Sync entrypoint (suitable to expose as an MCP tool) that:

- Cancels the in-flight asyncio Task if registered.
- Sets a short-lived cancellation flag for the key.
- Returns a small status payload.

Important: cancellation is process-local. It is designed for the common
single-process dev setup and "Stop this request" semantics.

#### `register_task(job_id|conversation_id, task)`

Associates the current asyncio Task with the cancellation key.

If a cancellation flag already exists (user cancelled slightly before
registration), this function will cancel the task immediately.

Typical usage pattern in a wrapper like an LLM handler:

```python
task = asyncio.current_task()
register_task(conversation_id=conversation_id, job_id=job_id, task=task)
try:
    return await provider_call()
finally:
    unregister_task(conversation_id=conversation_id, job_id=job_id)
```

#### `unregister_task(job_id|conversation_id)`

Clears the task reference and removes the token from the internal map to avoid
leaking tokens across requests.

#### `is_cancelled(job_id|conversation_id) -> bool`

Returns `True` only when the short-lived cancellation flag is present and within
TTL. It intentionally does NOT consult token state, to avoid sticky cancellation.

#### `register_cancellation(...) / unregister_cancellation(...)`

Legacy helpers that create/remove a token entry. In the current design, tokens
are only needed to hold a currently running task. Most integrations should use
`register_task/unregister_task` instead.

### TTL Semantics

`_CANCEL_TTL_SECONDS` controls how long the cancellation flag remains active.

- Too large: subsequent prompts in the same conversation could be cancelled.
- Too small: multi-step pipelines might miss the cancellation window if they
  don’t check frequently.

The flag auto-clears via a daemon thread.

### Complete Export List

The following symbols are exported by `common_adapters.cancel_convesation` (see `__init__.py`):

```python
CancelledError
CancellationToken
cancel_conversation
is_cancelled
register_cancellation
register_task
unregister_cancellation
unregister_task
```

### Provider Limitations

Some providers execute blocking network calls inside a thread pool
(`run_in_executor`). Cancelling the awaiting asyncio Task returns control
immediately to the server, but the underlying thread may still complete in the
background. This is a Python limitation; threads cannot be force-killed safely.

The user-visible behavior is still correct: the request returns "cancelled"
immediately and the UI does not wait for model output.

### Recommended Integration Pattern

1. Wrap all long-running LLM calls with `register_task/unregister_task`.
2. In multi-step tools, check `is_cancelled(...)`:
   - before starting a major step
   - between major steps
   - before persisting final output
3. Catch `asyncio.CancelledError` and return a deterministic response:

```python
except asyncio.CancelledError:
    return {"status": "success", "role": "assistant", "content": "Request cancelled.", "cancelled": True}
```

This combination guarantees:

- Immediate stop when cancel hits during an in-flight await.
- Race-safe stop when cancel arrives slightly before task registration.
- No sticky cancellation across subsequent prompts.
