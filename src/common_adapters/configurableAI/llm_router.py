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

    Special case: If agent_id = -1, always return azure provider.

    Args:
        workspace_id: Workspace ID (from user's auth context).
        agent_id: Agent ID (your agent's numeric ID in the system).

    Returns:
        Ready-to-use ConfigurableAIManager with current_provider set.

    Raises:
        ValueError: If no LLM is configured and auto-provisioning fails.
    """
    # Special case: agent_id = -1 should always return azure provider
    if agent_id == -1:
        logger.debug(f"Agent ID is -1, returning azure provider for workspace {workspace_id}")
        manager = ConfigurableAIManager()
        
        # Try to get azure provider config from database
        azure_config = llm_router_config_store.build_config_dict(workspace_id, "azure")
        if azure_config:
            try:
                manager.configure_provider("azure", azure_config)
                manager.set_current_provider("azure")
                logger.debug(f"Successfully configured azure provider for agent_id = -1 in workspace {workspace_id}")
                return manager
            except Exception as e:
                logger.warning(f"Failed to configure azure provider for agent_id = -1: {e}")
        
        # Fallback: auto-provision azure from environment variables
        provisioned = _auto_provision_workspace_config(workspace_id)
        if provisioned:
            azure_config = llm_router_config_store.build_config_dict(workspace_id, "azure")
            if azure_config:
                try:
                    manager.configure_provider("azure", azure_config)
                    manager.set_current_provider("azure")
                    logger.info(f"Auto-provisioned and configured azure provider for agent_id = -1 in workspace {workspace_id}")
                    return manager
                except Exception as e:
                    logger.error(f"Failed to configure auto-provisioned azure provider for agent_id = -1: {e}")
        
        raise ValueError(
            f"Cannot configure azure provider for agent_id = -1 in workspace {workspace_id}. "
            "Ensure azure provider is configured via admin_configure_llm_provider or set "
            "AZURE_OPENAI_LLM_MODEL_* environment variables."
        )

    key = _cache_key(workspace_id, agent_id)
    if key in _manager_cache:
        logger.debug(f"Returning cached LLM manager for workspace {workspace_id}, agent {agent_id}")
        return _manager_cache[key]

    logger.debug(f"Creating new LLM manager for workspace {workspace_id}, agent {agent_id}")
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
    current_model = config.get("current_model")

    successfully_configured_providers = []
    
    for provider in configured_providers:
        # Use current_model for the active provider; for other providers use their first configured model
        if provider == current_provider and current_model:
            model_override = current_model
        else:
            # Use first model from configured_models for this provider
            configured_models = config.get("configured_models") or {}
            provider_models = configured_models.get(provider) or []
            model_override = provider_models[0] if provider_models else None
        
        # Build config dict with enhanced deployment name resolution
        creds_dict = llm_router_config_store.build_config_dict(workspace_id, provider, model_override=model_override)
        if creds_dict:
            try:
                manager.configure_provider(provider, creds_dict)
                successfully_configured_providers.append(provider)
                logger.debug(f"Successfully configured provider '{provider}' for workspace {workspace_id}")
            except Exception as e:
                logger.warning(f"Could not configure provider '{provider}' for workspace {workspace_id}: {e}")
        else:
            logger.warning(f"No credentials found for provider '{provider}' in workspace {workspace_id}")

    # Set current provider only if it was successfully configured
    if current_provider and current_provider in successfully_configured_providers:
        try:
            manager.set_current_provider(current_provider)
            logger.debug(f"Set current provider to '{current_provider}' for workspace {workspace_id}, agent {agent_id}")
        except Exception as e:
            logger.warning(f"Could not set current provider '{current_provider}' for workspace {workspace_id}: {e}")
    elif successfully_configured_providers:
        # Fallback to first successfully configured provider
        fallback_provider = successfully_configured_providers[0]
        try:
            manager.set_current_provider(fallback_provider)
            logger.info(f"Current provider '{current_provider}' not available, using fallback '{fallback_provider}' for workspace {workspace_id}")
        except Exception as e:
            logger.warning(f"Could not set fallback provider '{fallback_provider}' for workspace {workspace_id}: {e}")

    # Cache the configured manager
    _manager_cache[key] = manager
    logger.debug(f"Cached LLM manager for workspace {workspace_id}, agent {agent_id} with {len(successfully_configured_providers)} providers")
    return manager


def invalidate_llm_cache(
    workspace_id: Optional[int] = None,
    agent_id: Optional[int] = None,
) -> None:
    """
    Enhanced cache invalidation with proper workspace isolation.
    
    This function ensures that cache invalidation respects workspace boundaries
    and properly handles both agent-specific and workspace-wide cache clearing.

    Args:
        workspace_id: Clear cache for this workspace. None = clear all.
        agent_id: Clear cache for this specific agent. None = clear all agents in workspace.
    """
    global _manager_cache

    if workspace_id is None:
        # Clear all caches globally
        _manager_cache.clear()
        clear_ai_manager_cache()
        logger.info("Cleared all LLM manager cache globally")
        return

    # Workspace-specific cache invalidation
    if agent_id is not None:
        # Clear cache for specific workspace-agent combination
        key = _cache_key(workspace_id, agent_id)
        removed = _manager_cache.pop(key, None)
        if removed:
            logger.info(f"Cleared LLM manager cache for workspace {workspace_id}, agent {agent_id}")
        else:
            logger.debug(f"No cache entry found for workspace {workspace_id}, agent {agent_id}")
    else:
        # Clear all cache entries for the entire workspace
        keys_to_remove = [k for k in _manager_cache if k.startswith(f"ws_{workspace_id}_")]
        removed_count = 0
        for k in keys_to_remove:
            del _manager_cache[k]
            removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cleared {removed_count} LLM manager cache entries for workspace {workspace_id}")
        else:
            logger.debug(f"No cache entries found for workspace {workspace_id}")

    # Clear provider-level cache for the workspace
    # This ensures that any provider-specific caching is also invalidated
    try:
        clear_ai_manager_cache(workspace_id=workspace_id, agent_id=agent_id)
    except Exception as e:
        logger.warning(f"Failed to clear AI manager cache for workspace {workspace_id}, agent {agent_id}: {e}")
    
    # Log cache state for debugging
    remaining_entries = len(_manager_cache)
    logger.debug(f"LLM cache invalidation complete. Remaining cache entries: {remaining_entries}")
