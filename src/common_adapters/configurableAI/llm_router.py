"""
LLM Router — High-level convenience functions for agents.

Any agent can use these to get a ready-to-use ConfigurableAIManager
pre-loaded with workspace/agent LLM configuration from MongoDB.

Usage:
    from common_adapters.configurableAI import get_configured_llm_manager, invalidate_llm_cache

    # Get a manager (cached per workspace+agent)
    manager = get_configured_llm_manager(workspace_id=782, agent_id=5)
    response = await manager.generate_text_async("Hello")

    # After switching provider, invalidate cache
    invalidate_llm_cache(workspace_id=782, agent_id=5)
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from .manager import ConfigurableAIManager, clear_ai_manager_cache
from .llm_router_config_store import llm_router_config_store

logger = logging.getLogger(__name__)

# In-memory cache: workspace+agent → manager instance
_manager_cache: Dict[str, ConfigurableAIManager] = {}


def _cache_key(workspace_id: int, agent_id: Optional[int]) -> str:
    return f"ws_{workspace_id}_agent_{agent_id}"


def _auto_provision_workspace_config(workspace_id: int) -> bool:
    """
    Auto-provision workspace LLM config from environment variables if not present.

    This allows fresh deployments (new MongoDB cluster) to work without manual
    admin_configure_llm_provider calls — just set the AZURE_OPENAI_LLM_MODEL_*
    environment variables and the workspace config is created on first access.

    Returns True if provisioning succeeded, False otherwise.
    """
    azure_api_key = os.getenv("AZURE_OPENAI_LLM_MODEL_API_KEY", "").strip()
    azure_endpoint = os.getenv("AZURE_OPENAI_LLM_MODEL_API_BASE", "").strip()
    azure_model = os.getenv("AZURE_OPENAI_LLM_MODEL_LLM_MODEL", "").strip()
    azure_api_version = os.getenv("AZURE_OPENAI_LLM_MODEL_API_VERSION", "").strip()

    if not (azure_api_key and azure_endpoint and azure_model):
        logger.warning(
            f"Cannot auto-provision LLM config for workspace {workspace_id}: "
            "AZURE_OPENAI_LLM_MODEL_API_KEY, AZURE_OPENAI_LLM_MODEL_API_BASE, "
            "or AZURE_OPENAI_LLM_MODEL_LLM_MODEL env vars are missing."
        )
        return False

    try:
        llm_router_config_store.upsert_provider_credentials(
            workspace_id=workspace_id,
            provider_name="azure",
            api_key=azure_api_key,
            endpoint=azure_endpoint,
            model=azure_model,
            api_version=azure_api_version or None,
            deployment_name=azure_model,
            user_id=None,
        )
        llm_router_config_store.create_or_update_configuration(
            workspace_id=workspace_id,
            agent_id=None,
            configured_providers=["azure"],
            current_provider="azure",
            user_id=None,
        )
        logger.info(
            f"Auto-provisioned default Azure LLM config for workspace {workspace_id} from env vars."
        )
        return True
    except Exception as e:
        logger.error(f"Failed to auto-provision LLM config for workspace {workspace_id}: {e}")
        return False


def get_configured_llm_manager(
    workspace_id: int,
    agent_id: Optional[int] = None,
) -> ConfigurableAIManager:
    """
    Get a ConfigurableAIManager pre-loaded with the workspace/agent's
    configured LLM provider from MongoDB.

    Results are cached in-memory. Call invalidate_llm_cache() after
    configuration changes (admin_configure, switch_provider, etc.).

    If no configuration exists for the workspace, auto-provisions one from
    AZURE_OPENAI_LLM_MODEL_* environment variables so that fresh deployments
    work without manual setup.

    Args:
        workspace_id: Workspace ID (from user's auth context).
        agent_id: Agent ID (your agent's numeric ID in the system).

    Returns:
        Ready-to-use ConfigurableAIManager with current_provider set.

    Raises:
        ValueError: If no LLM is configured and auto-provisioning fails.
    """
    key = _cache_key(workspace_id, agent_id)
    if key in _manager_cache:
        return _manager_cache[key]

    manager = ConfigurableAIManager()
    config = llm_router_config_store.get_effective_configuration(workspace_id, agent_id)

    # Auto-provision from env vars if no config exists for this workspace
    if not config:
        provisioned = _auto_provision_workspace_config(workspace_id)
        if provisioned:
            config = llm_router_config_store.get_effective_configuration(workspace_id, agent_id)

    if not config:
        raise ValueError(
            f"No LLM configured for workspace {workspace_id}, agent {agent_id}, "
            "and auto-provisioning from environment variables failed. "
            "Ensure AZURE_OPENAI_LLM_MODEL_API_KEY, AZURE_OPENAI_LLM_MODEL_API_BASE, "
            "and AZURE_OPENAI_LLM_MODEL_LLM_MODEL env vars are set, or configure "
            "via admin_configure_llm_provider."
        )

    configured_providers = config.get("configured_providers") or []
    current_provider = config.get("current_provider")

    for provider in configured_providers:
        creds_dict = llm_router_config_store.build_config_dict(workspace_id, provider)
        if creds_dict:
            try:
                manager.configure_provider(provider, creds_dict)
            except Exception as e:
                logger.warning(f"Could not configure provider '{provider}': {e}")
        else:
            logger.warning(f"No credentials found for provider '{provider}' in workspace {workspace_id}")

    if current_provider and current_provider in manager.list_configured_providers():
        try:
            manager.set_current_provider(current_provider)
        except Exception as e:
            logger.warning(f"Could not set current provider '{current_provider}': {e}")

    _manager_cache[key] = manager
    return manager


def invalidate_llm_cache(
    workspace_id: Optional[int] = None,
    agent_id: Optional[int] = None,
) -> None:
    """
    Invalidate cached LLM managers after configuration changes.

    Args:
        workspace_id: Clear cache for this workspace. None = clear all.
        agent_id: Clear cache for this specific agent. None = clear all agents in workspace.
    """
    global _manager_cache

    if workspace_id is None:
        _manager_cache.clear()
        clear_ai_manager_cache()
        logger.info("Cleared all LLM manager cache")
        return

    if agent_id is not None:
        key = _cache_key(workspace_id, agent_id)
        _manager_cache.pop(key, None)
    else:
        keys_to_remove = [k for k in _manager_cache if k.startswith(f"ws_{workspace_id}_")]
        for k in keys_to_remove:
            del _manager_cache[k]

    clear_ai_manager_cache(workspace_id=workspace_id, agent_id=agent_id)
    logger.info(f"Cleared LLM manager cache for workspace {workspace_id}, agent {agent_id}")
