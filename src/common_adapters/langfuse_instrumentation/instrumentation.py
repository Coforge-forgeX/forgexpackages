"""
Langfuse Auto-Instrumentation for PO Agent
===========================================

Compatible with langfuse v2+ (no langfuse.decorators required).

Instruments with full span details:
  1. FastMCP tools           → trace per tool call (user_id, session_id, workspace_id)
  2. AzureCustomLLM          → CallbackHandler injected → every LLM generation traced
  3. AzureChatOpenAI (bare)  → CallbackHandler injected (jira_agent / ado_agent)
  4. LangGraph graphs        → CallbackHandler injected at every CompiledGraph.ainvoke
  5. LightRAG RAG queries    → span with namespace + prompt metadata
  6. MCP sub-agent calls     → span around MCPClient.call_tool

Required env vars:
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_SECRET_KEY
  LANGFUSE_HOST        (optional, default https://cloud.langfuse.com)
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import inspect
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── module-level singletons ──────────────────────────────────────────────────
_langfuse = None   # Langfuse client
_handler  = None   # LangChain CallbackHandler
_enabled  = False
_trace_fn = None   # _langfuse.trace bound method, or None if unsupported

# ── per-request context (set at MCP tool boundary, read by LLM patches) ─────
_ctx_user_id      : contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("lf_user_id",      default=None)
_ctx_session_id   : contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("lf_session_id",   default=None)
_ctx_workspace_id : contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("lf_workspace_id", default=None)
_ctx_tool_name    : contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("lf_tool_name",    default=None)
# Parent trace context — set when a FastMCP tool trace is created, so that
# LangGraph/LLM child spans nest under the same trace instead of creating new roots.
_ctx_trace_id       : contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("lf_trace_id",       default=None)
_ctx_observation_id : contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("lf_observation_id", default=None)
# Live trace object — stored so ensure_trace_user_context() can update it from inside a tool
_ctx_trace_obj      : contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar("lf_trace_obj",      default=None)


# ── No-op stubs (used when tracing is unavailable) ─────────────────────────

class _NoOpSpan:
    def end(self, **kw): pass
    def update(self, **kw): pass

class _NoOpTrace:
    id = None
    trace_id = None
    def span(self, *a, **kw): return _NoOpSpan()
    def start_observation(self, *a, **kw): return _NoOpSpan()
    def generation(self, *a, **kw): return _NoOpSpan()
    def update(self, **kw): pass
    def end(self, **kw): pass


# ── v4 Adapters — wrap start_observation to match old trace.span() pattern ──

class _V4Span:
    """Wraps a Langfuse v4 observation to match the old span.end(output=...) interface."""
    def __init__(self, obs):
        self._obs = obs

    def end(self, output=None, level=None, status_message=None, **kw):
        try:
            update_kw = {}
            if output is not None:
                update_kw["output"] = output
            if level is not None:
                update_kw["level"] = level
            if status_message is not None:
                update_kw["status_message"] = status_message
            if update_kw:
                self._obs.update(**update_kw)
            self._obs.end()
        except Exception:
            pass

    def update(self, **kw):
        try:
            self._obs.update(**kw)
        except Exception:
            pass


class _V4Trace:
    """Wraps a Langfuse v4 observation to mimic old trace.span() / trace.update() interface."""
    def __init__(self, obs):
        self._obs = obs
        self.id = getattr(obs, "id", None)
        self.trace_id = getattr(obs, "trace_id", None)

    def span(self, name="span", input=None, **kw):
        try:
            child = self._obs.start_observation(name=name, as_type="span", input=input)
            return _V4Span(child)
        except Exception:
            return _NoOpSpan()

    def start_observation(self, name="span", as_type="span", input=None, metadata=None, **kw):
        """Expose v4's start_observation for direct child creation (used by RAG patches)."""
        try:
            return self._obs.start_observation(name=name, as_type=as_type, input=input, metadata=metadata)
        except Exception:
            return _NoOpSpan()

    def generation(self, name="generation", input=None, **kw):
        try:
            child = self._obs.start_observation(name=name, as_type="generation", input=input)
            return _V4Span(child)
        except Exception:
            return _NoOpSpan()

    def update(self, output=None, metadata=None, **kw):
        try:
            update_kw = {}
            if output is not None:
                update_kw["output"] = output
            if metadata is not None:
                update_kw["metadata"] = metadata
            if update_kw:
                self._obs.update(**update_kw)
        except Exception:
            pass

    def end(self, **kw):
        try:
            self._obs.end()
        except Exception:
            pass


def _make_trace(name: str, **kwargs):
    """
    Create a Langfuse trace/observation.

    Strategy:
      1. If SDK has .trace() (v2/v3) → use it directly.
      2. If SDK has .start_observation() (v4) → create observation with TraceContext.
      3. Otherwise → return _NoOpTrace.
    """
    # ── v2/v3 path ──────────────────────────────────────────────────────────
    if _trace_fn is not None:
        try:
            return _trace_fn(name=name, **kwargs)
        except Exception as exc:
            logger.debug("Langfuse trace() failed: %s", exc)

    # ── v4 path (start_observation + TraceContext) ──────────────────────────
    if _langfuse and hasattr(_langfuse, "start_observation"):
        try:
            from langfuse.types import TraceContext
            trace_ctx = {"name": name}
            if kwargs.get("user_id"):
                trace_ctx["user_id"] = kwargs["user_id"]
            if kwargs.get("session_id"):
                trace_ctx["session_id"] = kwargs["session_id"]

            obs = _langfuse.start_observation(
                name=name,
                as_type="span",
                trace_context=TraceContext(**trace_ctx),
                input=kwargs.get("input"),
                metadata=kwargs.get("metadata"),
            )
            return _V4Trace(obs)
        except Exception as exc:
            logger.debug("Langfuse v4 start_observation failed: %s", exc)

    return _NoOpTrace()


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def setup_langfuse() -> bool:
    """
    Initialise Langfuse and apply all monkey-patches.

    Call in main.py BEFORE tool-module imports.
    Returns True on success, False when disabled or unavailable.
    """
    global _langfuse, _handler, _enabled

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key  = os.getenv("LANGFUSE_SECRET_KEY",  "").strip()
    if not public_key or not secret_key:
        logger.warning(
            "⚠️  Langfuse tracing DISABLED — "
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set."
        )
        return False

    # ── verify langfuse core is importable ──────────────────────────────────
    try:
        from langfuse import Langfuse  # noqa: F401
    except ImportError as exc:
        logger.warning(
            "⚠️  langfuse package not installed — tracing disabled. "
            "Install: pip install langfuse  |  Error: %s", exc
        )
        return False

    # ── resolve CallbackHandler (v3 moved it; v2 kept it in .callback) ──────
    CallbackHandler = _resolve_callback_handler()
    if CallbackHandler is None:
        logger.warning(
            "⚠️  langfuse CallbackHandler not found — "
            "LangChain/LangGraph traces will be skipped. "
            "Upgrade: pip install --upgrade langfuse"
        )

    host    = os.getenv("LANGFUSE_HOST", "").strip()
    _kwargs = dict(public_key=public_key, secret_key=secret_key, host=host)

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(**_kwargs)
        _handler  = _build_callback_handler(CallbackHandler, public_key, secret_key, host)
        _enabled  = True

        # Resolve .trace() — present in v1/v2, removed/moved in some v3 builds
        global _trace_fn
        _trace_fn = getattr(_langfuse, "trace", None)
        if _trace_fn is None:
            if hasattr(_langfuse, "start_observation"):
                logger.info("🔭 Langfuse v4 detected — using start_observation() API")
            else:
                pass
        logger.info("🔭 Langfuse initialised — applying patches …")
        _patch_azure_custom_llm()
        _patch_azure_chat_openai()
        _patch_langgraph()
        _patch_lightrag()
        _patch_rag_pipeline()
        _patch_mcp_client()
        _patch_fastmcp_tool_decorator()
        logger.info("✅ Langfuse auto-instrumentation ACTIVE")
        return True

    except Exception as exc:
        logger.error("❌ Langfuse setup failed: %s", exc, exc_info=True)
        _enabled = False
        return False


def _resolve_callback_handler():
    """Return CallbackHandler class, trying v3 path then v2 path."""
    for module_path in ("langfuse.langchain", "langfuse.callback"):
        try:
            mod = __import__(module_path, fromlist=["CallbackHandler"])
            return getattr(mod, "CallbackHandler", None)
        except ImportError:
            continue
    return None


def _build_callback_handler(CallbackHandler, public_key: str, secret_key: str, host: str):
    """
    Build CallbackHandler across Langfuse SDK versions.

    - v4: CallbackHandler(public_key=...)
    - older versions may accept secret_key/host or no args
    """
    if CallbackHandler is None:
        return None

    candidate_kwargs = {
        "public_key": public_key,
        "secret_key": secret_key,
        "host": host,
    }

    try:
        sig = inspect.signature(CallbackHandler)
        params = sig.parameters
        accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

        if accepts_kwargs:
            return CallbackHandler(**candidate_kwargs)

        filtered_kwargs = {k: v for k, v in candidate_kwargs.items() if k in params}
        return CallbackHandler(**filtered_kwargs)
    except Exception:
        try:
            return CallbackHandler()
        except Exception as exc:
            logger.warning("⚠️  Failed to initialize Langfuse CallbackHandler: %s", exc)
            return None


def get_langfuse():
    """Return the global Langfuse client (None when disabled)."""
    return _langfuse


def get_handler():
    """Return the global LangChain/LangGraph CallbackHandler (None when disabled)."""
    return _handler


def is_enabled() -> bool:
    return _enabled


def flush():
    """Flush all pending Langfuse events. Call during graceful shutdown."""
    if _langfuse:
        try:
            _langfuse.flush()
            logger.info("✅ Langfuse events flushed")
        except Exception as exc:
            logger.warning("Langfuse flush error: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH 1 — AzureCustomLLM
# ═══════════════════════════════════════════════════════════════════════════

def _patch_azure_custom_llm():
    try:
        # AzureCustomLLM lives under different sub-packages depending on the agent:
        #   llm/azurecustomllm.py   → architect, businessanalyst, devagent, productowner, success-stories
        #   utils/azurecustomllm.py → kbcurator, ams_agent, qe
        #   tools/azurecustomllm.py → architect (secondary copy)
        AzureCustomLLM = None
        for _mod_path in (
            "llm.azurecustomllm",
            "utils.azurecustomllm",
            "tools.azurecustomllm",
        ):
            try:
                import importlib
                _mod = importlib.import_module(_mod_path)
                AzureCustomLLM = getattr(_mod, "AzureCustomLLM", None)
                if AzureCustomLLM is not None:
                    logger.info("  … AzureCustomLLM found at %s", _mod_path)
                    break
            except ImportError:
                continue

        if AzureCustomLLM is None:
            raise ImportError(
                "AzureCustomLLM not found in any of: "
                "llm.azurecustomllm, utils.azurecustomllm, tools.azurecustomllm"
            )

        _orig_init = AzureCustomLLM.__init__
        _orig_call = AzureCustomLLM._call

        @functools.wraps(_orig_init)
        def _patched_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            if _handler and hasattr(self, "_llm"):
                existing = list(self._llm.callbacks or [])
                if _handler not in existing:
                    self._llm.callbacks = existing + [_handler]

        @functools.wraps(_orig_call)
        def _patched_call(self, input, stop=None, sys_prompt=None, history=None, **kw):
            # inject user context so CallbackHandler tags the trace correctly
            _inject_user_metadata(self)
            return _orig_call(self, input, stop=stop, sys_prompt=sys_prompt, history=history, **kw)

        # Also patch BaseLLM.invoke so the outer LangChain trace gets session_id
        # (BaseLLM.invoke fires on_llm_start before _call; without this patch
        #  the outer trace has no user/session even though the inner one does)
        try:
            from langchain_core.language_models.llms import BaseLLM
            _orig_base_invoke = BaseLLM.invoke

            @functools.wraps(_orig_base_invoke)
            def _patched_base_invoke(self, input, config=None, **kw):
                config = _inject_user_config(config)
                return _orig_base_invoke(self, input, config=config, **kw)

            BaseLLM.invoke = _patched_base_invoke
        except Exception:
            pass  # non-critical — inner AzureChatOpenAI trace still has session

        AzureCustomLLM.__init__ = _patched_init
        AzureCustomLLM._call    = _patched_call
        logger.info("  ✓ AzureCustomLLM patched (init + _call + BaseLLM.invoke)")
    except Exception as exc:
        logger.warning("  ✗ AzureCustomLLM patch skipped: %s", exc)


def _inject_user_metadata(llm_instance):
    """
    Inject langfuse_user_id / langfuse_session_id into the underlying
    AzureChatOpenAI metadata so CallbackHandler tags the trace correctly.
    """
    user_id    = _ctx_user_id.get()
    session_id = _ctx_session_id.get()
    ws_id      = _ctx_workspace_id.get()
    if not (user_id or session_id) or not hasattr(llm_instance, "_llm"):
        return
    try:
        existing = dict(llm_instance._llm.metadata or {})
        if user_id:
            existing["langfuse_user_id"]    = user_id
        if session_id:
            existing["langfuse_session_id"] = session_id
        if ws_id:
            existing["workspace_id"]        = ws_id
        object.__setattr__(llm_instance._llm, "metadata", existing)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH 2 — AzureChatOpenAI (bare instances)
# ═══════════════════════════════════════════════════════════════════════════

def _patch_azure_chat_openai():
    try:
        from langchain_openai import AzureChatOpenAI

        # ── inject CallbackHandler at construction (robust for pydantic v1/v2) ──
        _orig_init = AzureChatOpenAI.__init__

        @functools.wraps(_orig_init)
        def _init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            if _handler:
                try:
                    existing = list(self.callbacks or [])
                    if _handler not in existing:
                        object.__setattr__(self, "callbacks", existing + [_handler])
                except Exception:
                    pass

        AzureChatOpenAI.__init__ = _init

        # ── inject user metadata at invoke time ──────────────────────────────
        _orig_ainvoke = AzureChatOpenAI.ainvoke
        _orig_invoke  = AzureChatOpenAI.invoke

        # In Langfuse v4 (OTel-based), setting langfuse_user_id / langfuse_session_id
        # in config metadata ONLY works for on_chain_start, NOT for standalone
        # on_chat_model_start calls. The correct v4 API is langfuse.propagate_attributes()
        # which sets OTel span attributes that Langfuse reads for trace user/session.
        _propagate_fn = None
        try:
            from langfuse import propagate_attributes as _propagate_fn_import
            _propagate_fn = _propagate_fn_import
        except ImportError:
            pass

        @functools.wraps(_orig_ainvoke)
        async def _ainvoke(self, input, config=None, **kw):
            config = _inject_user_config(config)
            user_id    = _ctx_user_id.get()
            session_id = _ctx_session_id.get()
            tool_name  = _ctx_tool_name.get() or "agent"
            if _propagate_fn and (user_id or session_id):
                with _propagate_fn(user_id=user_id, session_id=session_id, trace_name=tool_name):
                    return await _orig_ainvoke(self, input, config=config, **kw)
            return await _orig_ainvoke(self, input, config=config, **kw)

        @functools.wraps(_orig_invoke)
        def _invoke(self, input, config=None, **kw):
            config = _inject_user_config(config)
            user_id    = _ctx_user_id.get()
            session_id = _ctx_session_id.get()
            tool_name  = _ctx_tool_name.get() or "agent"
            if _propagate_fn and (user_id or session_id):
                with _propagate_fn(user_id=user_id, session_id=session_id, trace_name=tool_name):
                    return _orig_invoke(self, input, config=config, **kw)
            return _orig_invoke(self, input, config=config, **kw)

        AzureChatOpenAI.ainvoke = _ainvoke
        AzureChatOpenAI.invoke  = _invoke

        logger.info("  ✓ AzureChatOpenAI patched (callbacks + propagate_attributes)")
    except Exception as exc:
        logger.warning("  ✗ AzureChatOpenAI patch skipped: %s", exc)


def _inject_user_config(config: Optional[dict]) -> dict:
    """
    Merge Langfuse user/session context into a LangChain RunnableConfig.

    Keys the CallbackHandler reads:
      metadata["langfuse_user_id"]    → user in Langfuse UI
      metadata["langfuse_session_id"] → session in Langfuse UI
      metadata["langfuse_trace_name"] → trace name in Langfuse UI  (some builds)
      run_name                        → trace name in Langfuse UI  (all builds)
    """
    user_id    = _ctx_user_id.get()
    session_id = _ctx_session_id.get()
    ws_id      = _ctx_workspace_id.get()
    tool_name  = _ctx_tool_name.get() or "agent"
    trace_name = tool_name  # just the tool name — no prefix

    cfg  = dict(config) if config else {}
    meta = dict(cfg.get("metadata") or {})

    # always set run_name so trace is never "Unnamed"
    if "run_name" not in cfg:
        cfg["run_name"] = trace_name

    meta["langfuse_trace_name"] = trace_name  # for versions that read this key

    if user_id:
        meta["langfuse_user_id"]    = user_id
    if session_id:
        meta["langfuse_session_id"] = session_id
    if ws_id:
        meta["workspace_id"]        = ws_id

    cfg["metadata"] = meta
    return cfg


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH 3 — LangGraph CompiledGraph
# ═══════════════════════════════════════════════════════════════════════════

def _patch_langgraph():
    try:
        # CompiledGraph location varies by LangGraph version — try all known paths
        CompiledGraph = None
        for _mod_path, _cls in [
            ("langgraph.graph.graph",     "CompiledGraph"),
            ("langgraph.graph.compiled",  "CompiledGraph"),
            ("langgraph.pregel",          "Pregel"),        # LangGraph ≥0.2 base class
        ]:
            try:
                _m = __import__(_mod_path, fromlist=[_cls])
                CompiledGraph = getattr(_m, _cls, None)
                if CompiledGraph is not None:
                    break
            except ImportError:
                continue

        if CompiledGraph is None:
            logger.warning("  ✗ LangGraph patch skipped: CompiledGraph class not found in any known module path")
            return

        _orig_ainvoke = CompiledGraph.ainvoke
        _orig_invoke  = CompiledGraph.invoke
        _orig_astream = getattr(CompiledGraph, "astream", None)
        _orig_stream  = getattr(CompiledGraph, "stream",  None)

        @functools.wraps(_orig_ainvoke)
        async def _ainvoke(self, input, config=None, **kw):
            return await _orig_ainvoke(self, input, config=_inject_cb(config), **kw)

        @functools.wraps(_orig_invoke)
        def _invoke(self, input, config=None, **kw):
            return _orig_invoke(self, input, config=_inject_cb(config), **kw)

        CompiledGraph.ainvoke = _ainvoke
        CompiledGraph.invoke  = _invoke

        if _orig_astream:
            @functools.wraps(_orig_astream)
            async def _astream(self, input, config=None, **kw):
                async for chunk in _orig_astream(self, input, config=_inject_cb(config), **kw):
                    yield chunk
            CompiledGraph.astream = _astream

        if _orig_stream:
            @functools.wraps(_orig_stream)
            def _stream(self, input, config=None, **kw):
                yield from _orig_stream(self, input, config=_inject_cb(config), **kw)
            CompiledGraph.stream = _stream

        logger.info("  ✓ LangGraph CompiledGraph patched")
    except Exception as exc:
        logger.warning("  ✗ LangGraph patch skipped: %s", exc)


def _inject_cb(config: Optional[dict]) -> dict:
    """Merge CallbackHandler + user metadata into a LangChain RunnableConfig."""
    cfg = _inject_user_config(config)   # user_id / session_id into metadata
    if _handler:
        trace_id       = _ctx_trace_id.get()
        observation_id = _ctx_observation_id.get()
        cb = _handler
        # If a parent FastMCP trace is active, create a per-request handler bound
        # to that trace so LangGraph spans appear as children (not new L0 roots).
        if trace_id:
            try:
                # v4: use trace_context with trace_id
                from langfuse.types import TraceContext
                cb = type(_handler)(
                    trace_context=TraceContext(trace_id=trace_id),
                )
            except TypeError:
                cb = _handler
            except Exception:
                cb = _handler
        cbs = list(cfg.get("callbacks", []))
        if cb not in cbs:
            cbs.append(cb)
        cfg["callbacks"] = cbs
    return cfg


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH 4 — LightRAG query
# ═══════════════════════════════════════════════════════════════════════════

def _patch_lightrag():
    try:
        import utils.lightrag_wrapper as _lw
        _orig = _lw.lightrag_query

        @functools.wraps(_orig)
        async def _traced(prompt: str, namespace: dict, user_prompt: str = "", history: list = []):
            user_id    = _ctx_user_id.get()
            session_id = _ctx_session_id.get()
            ws_id      = _ctx_workspace_id.get()

            trace = _make_trace(
                "lightrag.query",
                user_id    = user_id,
                session_id = session_id,
                tags       = ["rag", "lightrag"],
                metadata   = {
                    "namespace":    namespace,
                    "history_len":  len(history),
                    "has_history":  bool(history),
                    "kb_url":       os.getenv("KBCURATOR_URL", ""),
                    "workspace_id": ws_id,
                },
                input={"prompt": prompt[:2000], "user_prompt": user_prompt[:500] if user_prompt else ""},
            )

            # ── connect phase ────────────────────────────────────────────────
            connect_span = trace.span(
                name  = "lightrag.connect",
                input = {"kb_url": os.getenv("KBCURATOR_URL", "")},
            )
            try:
                result = await _orig(prompt, namespace, user_prompt, history)

                # The original function handles connect + query internally;
                # we end connect span immediately after success to mark it done.
                connect_span.end(output={"status": "ok"})

                found_context = (
                    isinstance(result, str)
                    and result != "No relevant context found."
                    and "[no-context]" not in result
                )
                trace.update(
                    output   = result[:500] if isinstance(result, str) else None,
                    metadata = {
                        "namespace":     namespace,
                        "history_len":   len(history),
                        "has_history":   bool(history),
                        "kb_url":        os.getenv("KBCURATOR_URL", ""),
                        "workspace_id":  ws_id,
                        "found_context": found_context,
                        "result_len":    len(result) if isinstance(result, str) else 0,
                    },
                )
                return result

            except asyncio.TimeoutError as exc:
                connect_span.end(
                    level          = "ERROR",
                    status_message = "LightRAG timeout",
                    output         = {"error": "timeout"},
                )
                trace.update(metadata={"error": "timeout"})
                raise

            except Exception as exc:
                connect_span.end(
                    level          = "ERROR",
                    status_message = str(exc),
                    output         = {"error": str(exc)[:500]},
                )
                raise

        _lw.lightrag_query = _traced
        logger.info("  ✓ lightrag_query patched (LightRAG spans)")
    except Exception as exc:
        logger.warning("  ✗ lightrag_query patch skipped: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH 4b — Success-Stories RAG pipeline (vector search + LLM generation)
# ═══════════════════════════════════════════════════════════════════════════

def _patch_rag_pipeline():
    try:
        from utils.rag_pipeline import SuccessStoryChatBot

        # ── search (vector retrieval) ────────────────────────────────────────
        _orig_search = SuccessStoryChatBot.search

        @functools.wraps(_orig_search)
        def _traced_search(self, query: str, top_k: int = 5,
                           similarity_threshold: float = 0.5,
                           category_filter=None, previous_sources=None,
                           is_followup: bool = False):
            user_id    = _ctx_user_id.get()
            session_id = _ctx_session_id.get()

            # Use the parent trace object (v4) or parent trace_id (v2/v3) for nesting.
            parent_obj = _ctx_trace_obj.get()
            if parent_obj and hasattr(parent_obj, "start_observation"):
                # v4: create child observation under the parent tool trace
                try:
                    child_obs = parent_obj.start_observation(
                        name="rag.search",
                        as_type="retriever",
                        input={"query": query[:2000], "top_k": top_k, "category_filter": category_filter},
                        metadata={
                            "top_k":                top_k,
                            "similarity_threshold": similarity_threshold,
                            "is_followup":          is_followup,
                            "has_previous":         bool(previous_sources),
                        },
                    )
                    try:
                        results = _orig_search(
                            self, query,
                            top_k=top_k,
                            similarity_threshold=similarity_threshold,
                            category_filter=category_filter,
                            previous_sources=previous_sources,
                            is_followup=is_followup,
                        )
                        unique_docs = len({r.get("file_name") for r in results}) if results else 0
                        child_obs.update(output={
                            "result_count": len(results) if results else 0,
                            "unique_docs":  unique_docs,
                            "top_scores":   [round(r.get("similarity", 0), 4) for r in (results or [])[:3]],
                        })
                        child_obs.end()
                        return results
                    except Exception as exc:
                        child_obs.update(level="ERROR", status_message=str(exc))
                        child_obs.end()
                        raise
                except Exception:
                    pass  # fall through to old approach

            # Fallback: v2/v3 approach or standalone trace
            parent_trace_id = _ctx_trace_id.get()
            if parent_trace_id and _trace_fn:
                trace = _trace_fn(id=parent_trace_id)
            else:
                trace = _make_trace(
                    "rag.search",
                    user_id    = user_id,
                    session_id = session_id,
                    tags       = ["rag", "vector-search"],
                    metadata   = {
                        "top_k":                top_k,
                        "similarity_threshold": similarity_threshold,
                        "category_filter":      category_filter,
                        "is_followup":          is_followup,
                        "has_previous":         bool(previous_sources),
                    },
                    input={"query": query[:2000]},
                )

            span = trace.span(
                name  = "rag.vector_search",
                input = {"query": query[:2000], "top_k": top_k, "category_filter": category_filter},
            )
            try:
                results = _orig_search(
                    self, query,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                    category_filter=category_filter,
                    previous_sources=previous_sources,
                    is_followup=is_followup,
                )
                unique_docs = len({r.get("file_name") for r in results}) if results else 0
                span.end(output={
                    "result_count": len(results) if results else 0,
                    "unique_docs":  unique_docs,
                    "top_scores":   [round(r.get("similarity", 0), 4) for r in (results or [])[:3]],
                })
                return results
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        SuccessStoryChatBot.search = _traced_search

        # ── generate (LLM call) ──────────────────────────────────────────────
        # Patch structured_llm.invoke and llm.invoke on the class to always
        # pass Langfuse config (user_id, session_id as workspace_id) — same
        # pattern as PO agent uses via LangGraph _inject_cb.
        _orig_generate = SuccessStoryChatBot.generate_response_structured
        _orig_ss_init  = SuccessStoryChatBot.__init__

        class _LangfuseRunnableProxy:
            """Thin proxy that injects Langfuse metadata into every .invoke() call."""
            def __init__(self, wrapped):
                object.__setattr__(self, "_wrapped", wrapped)

            def __getattr__(self, name):
                return getattr(object.__getattribute__(self, "_wrapped"), name)

            def invoke(self, input, config=None, **kw):
                config = _inject_user_config(config)
                if _handler:
                    cbs = list(config.get("callbacks") or [])
                    if _handler not in cbs:
                        cbs.append(_handler)
                    config["callbacks"] = cbs
                return object.__getattribute__(self, "_wrapped").invoke(input, config=config, **kw)

            async def ainvoke(self, input, config=None, **kw):
                config = _inject_user_config(config)
                if _handler:
                    cbs = list(config.get("callbacks") or [])
                    if _handler not in cbs:
                        cbs.append(_handler)
                    config["callbacks"] = cbs
                return await object.__getattribute__(self, "_wrapped").ainvoke(input, config=config, **kw)

        @functools.wraps(_orig_ss_init)
        def _patched_ss_init(self, *args, **kwargs):
            _orig_ss_init(self, *args, **kwargs)
            # Wrap structured_llm and llm with proxy that injects metadata
            if hasattr(self, "structured_llm") and self.structured_llm is not None:
                self.__dict__["structured_llm"] = _LangfuseRunnableProxy(self.structured_llm)
            if hasattr(self, "llm") and self.llm is not None:
                self.__dict__["llm"] = _LangfuseRunnableProxy(self.llm)

        SuccessStoryChatBot.__init__ = _patched_ss_init

        @functools.wraps(_orig_generate)
        def _traced_generate(self, query: str, search_results, conversation_history=None):
            user_id    = _ctx_user_id.get()
            session_id = _ctx_session_id.get()

            # Use v4 parent trace object for nesting when available
            parent_obj = _ctx_trace_obj.get()
            if parent_obj and hasattr(parent_obj, "start_observation"):
                try:
                    child_obs = parent_obj.start_observation(
                        name="rag.generate",
                        as_type="chain",
                        input={
                            "query":          query[:2000],
                            "result_count":   len(search_results) if search_results else 0,
                            "history_turns":  len(conversation_history) if conversation_history else 0,
                        },
                        metadata={
                            "result_count":  len(search_results) if search_results else 0,
                            "has_history":   bool(conversation_history),
                            "history_turns": len(conversation_history) if conversation_history else 0,
                        },
                    )
                    try:
                        response = _orig_generate(self, query, search_results, conversation_history)
                        sources_count = len(response.get("sources", [])) if isinstance(response, dict) else 0
                        resp_text = response.get("response", "") if isinstance(response, dict) else str(response)
                        child_obs.update(output={
                            "response_len":  len(resp_text),
                            "sources_count": sources_count,
                            "preview":       resp_text[:300],
                        })
                        child_obs.end()
                        return response
                    except Exception as exc:
                        child_obs.update(level="ERROR", status_message=str(exc))
                        child_obs.end()
                        raise
                except Exception:
                    pass  # fall through to old approach

            # Fallback: v2/v3 approach or standalone trace
            parent_trace_id = _ctx_trace_id.get()
            if parent_trace_id and _trace_fn:
                trace = _trace_fn(id=parent_trace_id)
            else:
                trace = _make_trace(
                    "rag.generate",
                    user_id    = user_id,
                    session_id = session_id,
                    tags       = ["rag", "llm-generation"],
                    metadata   = {
                        "result_count":  len(search_results) if search_results else 0,
                        "has_history":   bool(conversation_history),
                        "history_turns": len(conversation_history) if conversation_history else 0,
                    },
                    input={"query": query[:2000]},
                )

            span = trace.span(
                name  = "rag.llm_generate",
                input = {
                    "query":          query[:2000],
                    "result_count":   len(search_results) if search_results else 0,
                    "history_turns":  len(conversation_history) if conversation_history else 0,
                },
            )
            try:
                response = _orig_generate(self, query, search_results, conversation_history)
                sources_count = len(response.get("sources", [])) if isinstance(response, dict) else 0
                resp_text = response.get("response", "") if isinstance(response, dict) else str(response)
                span.end(output={
                    "response_len":  len(resp_text),
                    "sources_count": sources_count,
                    "preview":       resp_text[:300],
                })
                trace.update(
                    output   = resp_text[:500],
                    metadata = {
                        "result_count":   len(search_results) if search_results else 0,
                        "has_history":    bool(conversation_history),
                        "history_turns":  len(conversation_history) if conversation_history else 0,
                        "sources_count":  sources_count,
                        "response_len":   len(resp_text),
                    },
                )
                return response
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        SuccessStoryChatBot.generate_response_structured = _traced_generate

        logger.info("  ✓ SuccessStoryChatBot patched (RAG search + generate spans)")
    except ImportError as exc:
        # utils.rag_pipeline is only present in the success-stories agent; skip
        # silently for all other agents. If this IS the success-stories agent and
        # the import is failing, enable DEBUG logging to see the full error.
        logger.debug("  ✓ rag_pipeline patch skipped (utils.rag_pipeline not found): %s", exc)
    except Exception as exc:
        logger.warning("  ✗ rag_pipeline patch skipped: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH 5 — MCPClient.call_tool (sub-agent calls)
# ═══════════════════════════════════════════════════════════════════════════

def _patch_mcp_client():
    try:
        from utils.stmhttp_client import MCPClient

        _orig_connect = MCPClient.connect_to_streamable_http_server

        @functools.wraps(_orig_connect)
        async def _traced_connect(self, url, headers=None, **kw):
            await _orig_connect(self, url, headers=headers, **kw)

            if not (hasattr(self, "session") and self.session is not None):
                return

            _orig_call = self.session.call_tool

            @functools.wraps(_orig_call)
            async def _traced_call(name: str, arguments=None, **ckw):
                trace = _make_trace(
                    f"mcp.call_tool:{name}",
                    metadata={"mcp_tool": name, "mcp_server": url},
                    input=_clean_input(arguments) if isinstance(arguments, dict) else arguments,
                )
                span = trace.span(
                    name=f"mcp.call_tool:{name}",
                    input=_clean_input(arguments) if isinstance(arguments, dict) else arguments,
                )
                try:
                    result = await _orig_call(name=name, arguments=arguments, **ckw)
                    span.end(output=_clean_output(result))
                    return result
                except Exception as exc:
                    span.end(level="ERROR", status_message=str(exc))
                    raise

            self.session.call_tool = _traced_call

        MCPClient.connect_to_streamable_http_server = _traced_connect
        logger.info("  ✓ MCPClient.call_tool patched (MCP sub-agent spans)")
    except Exception as exc:
        logger.warning("  ✗ MCPClient patch skipped: %s", exc)


def _safe_truncate(obj: Any, limit: int = 500) -> Any:
    """Truncate for metadata fields (returns string)."""
    if obj is None:
        return obj
    try:
        text = str(obj)
        return text[:limit] + "…" if len(text) > limit else text
    except Exception:
        return "<unserializable>"


def _clean_input(params: dict, limit: int = 2000) -> dict:
    """
    Return a clean dict for Langfuse input field.
    Truncates long string values so the UI renders them properly.
    """
    out = {}
    for k, v in params.items():
        if isinstance(v, str) and len(v) > limit:
            out[k] = v[:limit] + "…"
        elif isinstance(v, (dict, list, int, float, bool, type(None))):
            out[k] = v
        else:
            try:
                s = str(v)
                out[k] = s[:limit] + "…" if len(s) > limit else s
            except Exception:
                out[k] = "<unserializable>"
    return out


def _clean_output(result: Any, limit: int = 2000) -> Any:
    """
    Return a clean dict/str for Langfuse output field.
    Dicts are returned as-is (truncating long string values).
    Strings are returned directly (truncated).
    """
    if result is None:
        return None
    if isinstance(result, dict):
        return _clean_input(result, limit)  # same logic
    if isinstance(result, str):
        return result[:limit] + "…" if len(result) > limit else result
    try:
        s = str(result)
        return s[:limit] + "…" if len(s) > limit else s
    except Exception:
        return "<unserializable>"


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH 6 — FastMCP.tool() decorator
# ═══════════════════════════════════════════════════════════════════════════

def _patch_fastmcp_tool_decorator():
    try:
        from fastmcp import FastMCP

        _orig_tool = FastMCP.tool

        @functools.wraps(_orig_tool)
        def _patched_tool_method(self, *args, **kwargs):
            register = _orig_tool(self, *args, **kwargs)

            def _wrapping_decorator(func):
                tool_name = getattr(func, "__name__", "unknown")
                sig       = _safe_signature(func)

                has_user = _param_in_sig(sig, "user_id")
                has_ws   = _param_in_sig(sig, "workspace_id")

                if asyncio.iscoroutinefunction(func):
                    async def _async_traced(*fa, **fk):
                        return await _run_with_trace(
                            func, fa, fk, sig, tool_name, has_user, has_ws
                        )
                    _install_wrapper_attrs(_async_traced, func, sig)
                    return register(_async_traced)
                else:
                    def _sync_traced(*fa, **fk):
                        return _run_with_trace_sync(
                            func, fa, fk, sig, tool_name, has_user, has_ws
                        )
                    _install_wrapper_attrs(_sync_traced, func, sig)
                    return register(_sync_traced)

            return _wrapping_decorator

        FastMCP.tool = _patched_tool_method
        logger.info("  ✓ FastMCP.tool() patched (MCP tool traces)")
    except Exception as exc:
        logger.warning("  ✗ FastMCP.tool() patch skipped: %s", exc)


async def _run_with_trace(func, fa, fk, sig, tool_name, has_user, has_ws):
    params     = _bind_params(sig, fa, fk)
    user_id    = str(params["user_id"]).strip()      if has_user and "user_id"      in params else None
    ws_id      = str(params["workspace_id"]).strip() if has_ws   and "workspace_id" in params else None
    session_id = ws_id  # Langfuse session = workspace_id (same as PO agent)

    # ── set per-request context so LLM patches can read it ──────────────────
    tok_u = _ctx_user_id.set(user_id)
    tok_s = _ctx_session_id.set(session_id)
    tok_w = _ctx_workspace_id.set(ws_id)
    tok_t = _ctx_tool_name.set(tool_name)

    # Strip framework-injected params (e.g. ctx: Context) so they don't
    # pollute the Langfuse trace input or cause serialization failures.
    trace_params = _strip_inject_params(params, sig)

    trace = _make_trace(
        tool_name,
        user_id   = user_id,
        session_id= session_id,
        tags      = ["mcp-tool", tool_name],
        metadata  = {"tool": tool_name, "workspace_id": ws_id},
        input     = _clean_input(trace_params),
    )
    span = trace.span(name=tool_name, input=_clean_input(trace_params))

    # Store parent trace/span IDs so LangGraph child graphs nest under this trace
    tok_tr = _ctx_trace_id.set(getattr(trace, "id", None))
    tok_ob = _ctx_observation_id.set(getattr(span, "id", None))
    tok_to = _ctx_trace_obj.set(trace)

    try:
        result = await func(*fa, **fk)
        span.end(output=_clean_output(result))
        trace.update(output=_clean_output(result))
        return result
    except Exception as exc:
        span.end(level="ERROR", status_message=str(exc))
        raise
    finally:
        _ctx_user_id.reset(tok_u)
        _ctx_session_id.reset(tok_s)
        _ctx_workspace_id.reset(tok_w)
        _ctx_tool_name.reset(tok_t)
        _ctx_trace_id.reset(tok_tr)
        _ctx_observation_id.reset(tok_ob)
        _ctx_trace_obj.reset(tok_to)


def _run_with_trace_sync(func, fa, fk, sig, tool_name, has_user, has_ws):
    params     = _bind_params(sig, fa, fk)
    user_id    = str(params["user_id"]).strip()      if has_user and "user_id"      in params else None
    ws_id      = str(params["workspace_id"]).strip() if has_ws   and "workspace_id" in params else None
    session_id = ws_id  # Langfuse session = workspace_id (same as PO agent)

    tok_u = _ctx_user_id.set(user_id)
    tok_s = _ctx_session_id.set(session_id)
    tok_w = _ctx_workspace_id.set(ws_id)
    tok_t = _ctx_tool_name.set(tool_name)

    # Strip framework-injected params (e.g. ctx: Context) so they don't
    # pollute the Langfuse trace input or cause serialization failures.
    trace_params = _strip_inject_params(params, sig)

    trace = _make_trace(
        tool_name,
        user_id   = user_id,
        session_id= session_id,
        tags      = ["mcp-tool", tool_name],
        metadata  = {"tool": tool_name, "workspace_id": ws_id},
        input     = _clean_input(trace_params),
    )
    span = trace.span(name=tool_name, input=_clean_input(trace_params))

    # Store parent trace/span IDs so LangGraph child graphs nest under this trace
    tok_tr = _ctx_trace_id.set(getattr(trace, "id", None))
    tok_ob = _ctx_observation_id.set(getattr(span, "id", None))
    tok_to = _ctx_trace_obj.set(trace)

    try:
        result = func(*fa, **fk)
        span.end(output=_clean_output(result))
        trace.update(output=_clean_output(result))
        return result
    except Exception as exc:
        span.end(level="ERROR", status_message=str(exc))
        raise
    finally:
        _ctx_user_id.reset(tok_u)
        _ctx_session_id.reset(tok_s)
        _ctx_workspace_id.reset(tok_w)
        _ctx_tool_name.reset(tok_t)
        _ctx_trace_id.reset(tok_tr)
        _ctx_observation_id.reset(tok_ob)
        _ctx_trace_obj.reset(tok_to)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _safe_signature(func) -> Optional[inspect.Signature]:
    try:
        return inspect.signature(func)
    except (ValueError, TypeError):
        return None


def _param_in_sig(sig: Optional[inspect.Signature], name: str) -> bool:
    return sig is not None and name in sig.parameters


def _bind_params(sig: Optional[inspect.Signature], args, kwargs) -> dict:
    if sig:
        try:
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            return dict(bound.arguments)
        except Exception:
            pass
    return dict(kwargs)


def _install_wrapper_attrs(wrapper, func, sig: Optional[inspect.Signature]) -> None:
    """
    Copy metadata from func to wrapper for FastMCP schema introspection,
    setting __signature__ explicitly instead of __wrapped__.

    Why not @functools.wraps:  functools.wraps sets __wrapped__ = func.
    When FastMCP sees __wrapped__ on a registered tool and needs to inject
    ctx: Context, some versions follow __wrapped__ and call the original
    function directly — completely bypassing this instrumentation wrapper.
    Setting __signature__ gives inspect.signature() the correct parameter
    schema (including ctx: Context so FastMCP injects it) without exposing
    a __wrapped__ shortcut that lets FastMCP skip the wrapper.

    Safe for all agents: agents without ctx: Context are unaffected because
    FastMCP has no reason to follow __wrapped__ for them, but getting rid of
    __wrapped__ is harmless and makes the behaviour consistent everywhere.
    """
    for attr in ("__module__", "__name__", "__qualname__", "__doc__", "__annotations__"):
        try:
            setattr(wrapper, attr, getattr(func, attr))
        except (AttributeError, TypeError):
            pass
    try:
        wrapper.__dict__.update(func.__dict__)
    except AttributeError:
        pass
    # __signature__ takes priority over __wrapped__ in inspect.signature(),
    # so FastMCP gets the correct schema without a __wrapped__ bypass path.
    if sig is not None:
        wrapper.__signature__ = sig


def _strip_inject_params(params: dict, sig: Optional[inspect.Signature]) -> dict:
    """
    Remove FastMCP framework-injected parameters (e.g. ctx: Context) from
    params before passing to _clean_input / _make_trace.

    The ctx object is not JSON-serialisable in any meaningful way and can
    cause _make_trace to throw (caught silently as _NoOpTrace), which
    prevents the root Langfuse trace from being created with user_id /
    workspace_id.  Stripping it here fixes architect-agent tracing while
    being a no-op for every other agent (they have no Context params).
    """
    if not params or sig is None:
        return params
    try:
        from fastmcp import Context as _FastMCPContext
    except ImportError:
        return params
    result = {}
    for k, v in params.items():
        param = sig.parameters.get(k)
        if param is not None:
            ann = param.annotation
            if ann is not inspect.Parameter.empty:
                try:
                    if isinstance(ann, type) and issubclass(ann, _FastMCPContext):
                        continue
                except TypeError:
                    pass
        result[k] = v
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC HELPER — explicit trace user-context update
# ═══════════════════════════════════════════════════════════════════════════
def ensure_trace_user_context(
    user_id: Optional[str],
    workspace_id: Optional[str],
    tool_name: str = "mcp-tool",
) -> None:
    """
    Guarantee the current Langfuse trace has user_id and session_id set.

    Call this at the start of any FastMCP tool that has ctx: Context as its
    first parameter (the architect-agent pattern). The instrumentation wrapper
    may not be able to extract those values when ctx occupies the first
    positional slot, so calling this directly from inside the tool is the
    reliable fallback.

    Behaviour:
    - If the wrapper already created a trace, updates it with the correct ids.
    - If no trace exists yet (wrapper was bypassed), creates a new one.
    - Also seeds the per-request context vars so that downstream LLM / LangGraph
      patches can read user_id and session_id.
    - No-op when tracing is disabled or user_id/workspace_id are both empty.
    """
    if not _enabled or _trace_fn is None:
        return

    uid = str(user_id)    if user_id    else None
    sid = str(workspace_id) if workspace_id else None
    if not uid and not sid:
        return

    # Always keep context vars in sync so LLM patches have the right values.
    if uid:
        _ctx_user_id.set(uid)
    if sid:
        _ctx_session_id.set(sid)
        _ctx_workspace_id.set(sid)

    # Use the trace ID stored by the wrapper (if it ran) to update that trace.
    # Calling _trace_fn(id=existing_id, ...) is how the Langfuse SDK merges
    # fields into an existing trace rather than creating a duplicate.
    existing_trace_id = _ctx_trace_id.get()
    try:
        if existing_trace_id:
            _trace_fn(id=existing_trace_id, user_id=uid, session_id=sid)
            logger.debug("ensure_trace_user_context: updated trace %s uid=%s sid=%s",
                         existing_trace_id, uid, sid)
        else:
            new_trace = _trace_fn(
                name=tool_name,
                user_id=uid,
                session_id=sid,
                tags=["mcp-tool", tool_name],
                metadata={"tool": tool_name, "workspace_id": workspace_id},
            )
            new_id = getattr(new_trace, "id", None)
            _ctx_trace_id.set(new_id)
            logger.debug("ensure_trace_user_context: created trace %s uid=%s sid=%s",
                         new_id, uid, sid)
    except Exception as exc:
        logger.warning("ensure_trace_user_context failed: %s", exc)
