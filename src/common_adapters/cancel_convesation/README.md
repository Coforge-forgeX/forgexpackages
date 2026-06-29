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
