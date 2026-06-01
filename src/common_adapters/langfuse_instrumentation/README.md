# langfuse_instrumentation — Integration Guide

## 1. Install in the agent

**`Dockerfile`**
```dockerfile
COPY packages/langfuse_instrumentation /packages/langfuse_instrumentation
RUN pip install /packages/langfuse_instrumentation
```

**`requirements.txt`** (local dev)
```
langfuse>=2.0.0
langchain-core>=0.1.0
```

---

## 2. Environment variables

```env
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=""  # optional
```

---

## 3. `main.py` — call `setup_langfuse()` before any tool imports

```python
from dotenv import load_dotenv
load_dotenv()

from langfuse_instrumentation import setup_langfuse
setup_langfuse()   # must be before tool/server imports

from server import mcp
# ... rest of main.py
```

---

## 4. `server.py` — flush on shutdown

```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP

@asynccontextmanager
async def lifespan(app):
    yield
    try:
        from langfuse_instrumentation import flush as langfuse_flush
        langfuse_flush()
    except Exception:
        pass

mcp = FastMCP(name="My Agent", lifespan=lifespan)
```

---

## 5. Tools — no changes needed

Any `@mcp.tool()` that accepts `user_id`, `conversation_id` will have those values automatically propagated to all downstream LLM/graph/RAG traces.

```python
@mcp.tool()
async def my_tool(query: str, user_id: str, conversation_id: str, workspace_id: str) -> str:
    # all traces created here are automatically tagged with user/session context
    ...
```
