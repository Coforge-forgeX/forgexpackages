"""
LLM Router Config Store — MongoDB-backed storage for LLM router credentials
and provider selection. Moved here so all agents can use it via common_adapters
without depending on kbcurator.

Usage:
    from common_adapters.configurableAI.llm_router_config_store import llm_router_config_store
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import logging
import os
import threading

import certifi
from pymongo import MongoClient

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ["azure", "quasar"]
DEFAULT_CONFIG_KEY = "__workspace_default__"
LLM_CONFIG_DB_NAME = "llm_configs"
LLM_CONFIG_COLLECTION_NAME = "workspace_configs"


# ---------------------------------------------------------------------------
# Lightweight MongoDB singleton for the config store
# ---------------------------------------------------------------------------

_mongo_client: Optional[MongoClient] = None
_mongo_lock = threading.Lock()


def _get_mongo_client() -> MongoClient:
    """Return a module-level singleton MongoClient (thread-safe)."""
    global _mongo_client
    if _mongo_client is None:
        with _mongo_lock:
            if _mongo_client is None:
                uri = os.getenv("MONGODB_DATABASE_URI", "").strip()
                if not uri:
                    raise ValueError(
                        "MONGODB_DATABASE_URI environment variable is required for LLM Router config store."
                    )
                _mongo_client = MongoClient(
                    uri,
                    tlsCAFile=certifi.where(),
                    maxPoolSize=10,
                    minPoolSize=0,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    retryWrites=True,
                    retryReads=True,
                )
    return _mongo_client


# ---------------------------------------------------------------------------
# Config Store
# ---------------------------------------------------------------------------


class LLMRouterConfigStore:
    """CRUD abstraction over a single MongoDB config document per workspace."""

    def __init__(self):
        self._collection = None
        self._indexes_ready = False

    def _get_collection(self):
        """Lazy initialization — connects to MongoDB on first use."""
        if self._collection is None:
            client = _get_mongo_client()
            self._collection = client[LLM_CONFIG_DB_NAME][LLM_CONFIG_COLLECTION_NAME]
            self._ensure_indexes()
        return self._collection

    def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        # Deduplicate any existing documents before creating unique index
        self._deduplicate_workspace_documents()
        self._collection.create_index("workspace_id", unique=True, name="uq_workspace_id")
        self._collection.create_index("updated_at", name="idx_updated_at")
        self._indexes_ready = True

    def _deduplicate_workspace_documents(self) -> None:
        """Remove duplicate workspace documents, keeping the most recently updated one."""
        try:
            pipeline = [
                {"$group": {
                    "_id": "$workspace_id",
                    "count": {"$sum": 1},
                    "docs": {"$push": {"_id": "$_id", "updated_at": "$updated_at"}},
                }},
                {"$match": {"count": {"$gt": 1}}},
            ]
            duplicates = list(self._collection.aggregate(pipeline))
            for dup in duplicates:
                docs = sorted(
                    dup["docs"],
                    key=lambda d: d.get("updated_at") or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True,
                )
                # Keep the first (most recent), delete the rest
                ids_to_delete = [d["_id"] for d in docs[1:]]
                if ids_to_delete:
                    self._collection.delete_many({"_id": {"$in": ids_to_delete}})
                    logger.info(
                        f"Deduplicated workspace_id={dup['_id']}: removed {len(ids_to_delete)} duplicate(s)"
                    )
        except Exception as e:
            logger.warning(f"Deduplication check failed (non-fatal): {e}")

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _agent_key(agent_id: Optional[int]) -> str:
        return str(agent_id) if agent_id is not None else DEFAULT_CONFIG_KEY

    def _ensure_workspace_document(self, workspace_id: int) -> None:
        now = self._utcnow()
        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$setOnInsert": {
                    "workspace_id": workspace_id,
                    "provider_credentials": {},
                    "agent_configs": {},
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

    def _get_workspace_document(self, workspace_id: int) -> Optional[Dict[str, Any]]:
        return self._get_collection().find_one({"workspace_id": workspace_id})

    # ------------------------------------------------------------------
    # Provider credentials
    # ------------------------------------------------------------------

    def get_provider_credentials(self, workspace_id: int, provider_name: str) -> Optional[Dict[str, Any]]:
        provider = provider_name.lower().strip()
        doc = self._get_workspace_document(workspace_id)
        if not doc:
            return None

        entry = (doc.get("provider_credentials") or {}).get(provider)
        if not entry or not entry.get("is_active", True):
            return None

        return {
            "workspace_id": workspace_id,
            "provider_name": provider,
            "api_key": entry.get("api_key"),
            "endpoint": entry.get("endpoint"),
            "model": entry.get("model"),
            "api_version": entry.get("api_version"),
            "deployment_name": entry.get("deployment_name"),
            "available_models": entry.get("available_models") or [],
            "model_assignments": entry.get("model_assignments") or {},
            "extra_config": entry.get("extra_config") or {},
            "is_active": True,
            "created_at": entry.get("created_at"),
            "updated_at": entry.get("updated_at"),
            "created_by": entry.get("created_by"),
            "updated_by": entry.get("updated_by"),
        }

    def list_workspace_providers(self, workspace_id: int) -> List[Dict[str, Any]]:
        doc = self._get_workspace_document(workspace_id)
        if not doc:
            return []

        providers = []
        for provider_name in sorted((doc.get("provider_credentials") or {}).keys()):
            creds = self.get_provider_credentials(workspace_id, provider_name)
            if creds:
                providers.append(creds)
        return providers

    def resolve_deployment_name(self, workspace_id: int, provider: str, model_name: str) -> str:
        """
        Resolve Azure deployment name from model name.
        
        For Azure OpenAI, deployment_name is the actual deployment identifier,
        while model_name is the logical model identifier. This method maps
        between them using the available_models configuration.
        
        Args:
            workspace_id: Workspace ID
            provider: Provider name (should be 'azure' for this to matter)
            model_name: Logical model name (e.g., 'gpt-4')
            
        Returns:
            Deployment name for Azure, or model_name for other providers
        """
        if provider.lower().strip() != "azure":
            return model_name
        
        creds = self.get_provider_credentials(workspace_id, provider)
        if not creds:
            logger.warning(f"No credentials found for provider '{provider}' in workspace {workspace_id}")
            return model_name
            
        available_models = creds.get("available_models", [])
        
        # Look for exact model_name match in available_models
        for model_entry in available_models:
            if model_entry.get("model_name") == model_name:
                deployment_name = model_entry.get("deployment_name")
                if deployment_name:
                    logger.debug(f"Resolved model '{model_name}' to deployment '{deployment_name}' for workspace {workspace_id}")
                    return deployment_name
                break
        
        # Fallback: check if model_name matches the top-level model
        if creds.get("model") == model_name:
            deployment_name = creds.get("deployment_name")
            if deployment_name:
                logger.debug(f"Using top-level deployment '{deployment_name}' for model '{model_name}' in workspace {workspace_id}")
                return deployment_name
        
        # Final fallback: use model_name as deployment_name
        logger.debug(f"No deployment mapping found for model '{model_name}' in workspace {workspace_id}, using model name as deployment")
        return model_name

    def build_config_dict(self, workspace_id: int, provider_name: str, model_override: Optional[str] = None) -> Optional[Dict[str, Any]]:
        creds = self.get_provider_credentials(workspace_id, provider_name)
        if not creds:
            return None

        provider = provider_name.lower().strip()
        model = model_override or creds["model"]

        # Use the new deployment name resolution method
        deployment_name = self.resolve_deployment_name(workspace_id, provider, model)

        config = {
            "provider_name": provider,
            "api_key": creds["api_key"],
            "endpoint": creds["endpoint"],
            "model": model,
            "extra_params": creds.get("extra_config") or {},
        }
        if provider == "azure":
            config["deployment_name"] = deployment_name
            config["api_version"] = creds.get("api_version")
        return config

    def upsert_provider_credentials(
        self,
        workspace_id: int,
        provider_name: str,
        api_key: str,
        endpoint: str,
        model: str,
        api_version: Optional[str] = None,
        deployment_name: Optional[str] = None,
        extra_config: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        provider = provider_name.lower().strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Provider '{provider}' is not supported. Supported: {SUPPORTED_PROVIDERS}"
            )

        self._ensure_workspace_document(workspace_id)

        existing = self.get_provider_credentials(workspace_id, provider)
        now = self._utcnow()

        # Preserve existing available_models list, or initialize with the current model
        existing_models = []
        if existing:
            existing_models = existing.get("available_models") or []

        # Ensure the current model is in available_models
        model_entry = {"model_name": model, "deployment_name": deployment_name or model}
        if not any(m["model_name"] == model for m in existing_models):
            existing_models.append(model_entry)

        payload = {
            "api_key": api_key,
            "endpoint": endpoint,
            "model": model,
            "api_version": api_version,
            "deployment_name": deployment_name or model,
            "available_models": existing_models,
            "model_assignments": existing.get("model_assignments") or {} if existing else {},
            "extra_config": extra_config or {},
            "is_active": True,
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
            "created_by": existing.get("created_by") if existing else user_id,
            "updated_by": user_id,
        }

        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"provider_credentials.{provider}": payload,
                    "updated_at": now,
                }
            },
        )

        return self.get_provider_credentials(workspace_id, provider)

    def deactivate_provider_credentials(
        self,
        workspace_id: int,
        provider_name: str,
        user_id: Optional[int] = None,
    ) -> bool:
        provider = provider_name.lower().strip()
        doc = self._get_workspace_document(workspace_id)
        entry = ((doc or {}).get("provider_credentials") or {}).get(provider)
        if not entry or not entry.get("is_active", True):
            return False

        now = self._utcnow()
        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"provider_credentials.{provider}.is_active": False,
                    f"provider_credentials.{provider}.updated_at": now,
                    f"provider_credentials.{provider}.updated_by": user_id,
                    "updated_at": now,
                }
            },
        )
        return True

    # ------------------------------------------------------------------
    # Agent configuration
    # ------------------------------------------------------------------

    def _normalize_providers(self, providers: Optional[List[str]]) -> List[str]:
        values = []
        for provider in providers or []:
            p = provider.lower().strip()
            if p not in SUPPORTED_PROVIDERS:
                raise ValueError(f"Invalid provider: {p}")
            if p not in values:
                values.append(p)
        return values

    def get_configuration(self, workspace_id: int, agent_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        doc = self._get_workspace_document(workspace_id)
        if not doc:
            return None

        key = self._agent_key(agent_id)
        cfg = (doc.get("agent_configs") or {}).get(key)
        if not cfg or not cfg.get("is_active", True):
            return None

        return {
            "id": f"{workspace_id}:{key}",
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "configured_providers": cfg.get("configured_providers") or [],
            "configured_models": cfg.get("configured_models") or {},
            "current_provider": cfg.get("current_provider"),
            "current_model": cfg.get("current_model"),
            "created_at": cfg.get("created_at"),
            "updated_at": cfg.get("updated_at"),
            "created_by": cfg.get("created_by"),
            "updated_by": cfg.get("updated_by"),
        }

    def get_effective_configuration(self, workspace_id: int, agent_id: int) -> Optional[Dict[str, Any]]:
        return self.get_configuration(workspace_id, agent_id) or self.get_configuration(workspace_id, None)

    def create_or_update_configuration(
        self,
        workspace_id: int,
        agent_id: Optional[int] = None,
        configured_providers: Optional[List[str]] = None,
        configured_models: Optional[Dict[str, List[str]]] = None,
        current_provider: Optional[str] = None,
        current_model: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._ensure_workspace_document(workspace_id)
        existing = self.get_configuration(workspace_id, agent_id)

        providers = (
            self._normalize_providers(configured_providers)
            if configured_providers is not None
            else list(existing.get("configured_providers") or [])
            if existing
            else []
        )

        selected_provider = current_provider.lower().strip() if current_provider else None
        if selected_provider and selected_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Invalid provider: {selected_provider}")
        if selected_provider and selected_provider not in providers:
            providers.append(selected_provider)

        # Merge configured_models: keep existing, override with provided
        models_map = dict((existing or {}).get("configured_models") or {})
        if configured_models is not None:
            for prov, model_list in configured_models.items():
                models_map[prov] = list(model_list)

        # Resolve current_model
        resolved_model = current_model
        if resolved_model is None:
            resolved_model = (existing or {}).get("current_model")

        now = self._utcnow()
        key = self._agent_key(agent_id)
        payload = {
            "configured_providers": providers,
            "configured_models": models_map,
            "current_provider": selected_provider if current_provider is not None else (existing or {}).get("current_provider"),
            "current_model": resolved_model,
            "is_active": True,
            "created_at": (existing or {}).get("created_at", now),
            "updated_at": now,
            "created_by": (existing or {}).get("created_by", user_id),
            "updated_by": user_id,
        }

        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"agent_configs.{key}": payload,
                    "updated_at": now,
                }
            },
        )
        return self.get_configuration(workspace_id, agent_id)

    def switch_provider(
        self,
        workspace_id: int,
        provider: str,
        agent_id: Optional[int] = None,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Switch the active provider+model for an agent."""
        selected = provider.lower().strip()
        if selected not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Invalid provider: {selected}")

        cfg = self.get_configuration(workspace_id, agent_id)
        providers = list(cfg.get("configured_providers") or []) if cfg else []
        if selected not in providers:
            providers.append(selected)

        # Resolve model
        resolved_model = model
        if not resolved_model:
            # Use first configured model for this provider, or provider default
            configured_models = (cfg or {}).get("configured_models") or {}
            provider_models = configured_models.get(selected) or []
            if provider_models:
                resolved_model = provider_models[0]
            else:
                creds = self.get_provider_credentials(workspace_id, selected)
                if creds and creds.get("model"):
                    resolved_model = creds["model"]

        # Validate model exists in provider
        if resolved_model:
            creds = self.get_provider_credentials(workspace_id, selected)
            available_models = (creds or {}).get("available_models") or []
            if available_models and not any(m["model_name"] == resolved_model for m in available_models):
                raise ValueError(
                    f"Model '{resolved_model}' is not available for provider '{selected}'. "
                    f"Available: {[m['model_name'] for m in available_models]}"
                )

        return self.create_or_update_configuration(
            workspace_id=workspace_id,
            agent_id=agent_id,
            configured_providers=providers,
            current_provider=selected,
            current_model=resolved_model,
            user_id=user_id,
        )

    def add_provider(
        self,
        workspace_id: int,
        provider: str,
        agent_id: Optional[int] = None,
        set_as_current: bool = False,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Add a provider to an agent's configuration."""
        selected = provider.lower().strip()
        if selected not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Invalid provider: {selected}")

        cfg = self.get_configuration(workspace_id, agent_id)
        providers = list(cfg.get("configured_providers") or []) if cfg else []
        if selected not in providers:
            providers.append(selected)

        # Resolve model for the new provider
        resolved_model = model
        if not resolved_model:
            creds = self.get_provider_credentials(workspace_id, selected)
            if creds and creds.get("model"):
                resolved_model = creds["model"]

        # Add model to configured_models for this provider
        configured_models = dict((cfg or {}).get("configured_models") or {})
        provider_models = list(configured_models.get(selected) or [])
        if resolved_model and resolved_model not in provider_models:
            provider_models.append(resolved_model)
        configured_models[selected] = provider_models

        # Determine current_provider and current_model
        current_provider = selected if set_as_current else (cfg or {}).get("current_provider")
        current_model_val = None
        if set_as_current:
            current_model_val = resolved_model
        else:
            current_model_val = (cfg or {}).get("current_model")

        return self.create_or_update_configuration(
            workspace_id=workspace_id,
            agent_id=agent_id,
            configured_providers=providers,
            configured_models=configured_models,
            current_provider=current_provider,
            current_model=current_model_val,
            user_id=user_id,
        )

    def add_model_to_agent(
        self,
        workspace_id: int,
        provider: str,
        model: str,
        agent_id: Optional[int] = None,
        set_as_current: bool = False,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Add a specific model to an agent's configured_models for a provider."""
        selected = provider.lower().strip()
        cfg = self.get_configuration(workspace_id, agent_id)

        providers = list(cfg.get("configured_providers") or []) if cfg else []
        if selected not in providers:
            providers.append(selected)

        configured_models = dict((cfg or {}).get("configured_models") or {})
        provider_models = list(configured_models.get(selected) or [])
        if model not in provider_models:
            provider_models.append(model)
        configured_models[selected] = provider_models

        # Also ensure the model is in the provider's available_models list
        self._ensure_model_in_provider_available_models(workspace_id, selected, model)

        current_provider = (cfg or {}).get("current_provider")
        current_model_val = (cfg or {}).get("current_model")
        if set_as_current:
            current_provider = selected
            current_model_val = model

        return self.create_or_update_configuration(
            workspace_id=workspace_id,
            agent_id=agent_id,
            configured_providers=providers,
            configured_models=configured_models,
            current_provider=current_provider,
            current_model=current_model_val,
            user_id=user_id,
        )

    def remove_model_from_agent(
        self,
        workspace_id: int,
        provider: str,
        model: str,
        agent_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Remove a specific model from an agent's configured_models for a provider."""
        selected = provider.lower().strip()
        cfg = self.get_configuration(workspace_id, agent_id)
        
        if not cfg:
            logger.warning(f"No configuration found for workspace {workspace_id}, agent {agent_id}")
            return {}

        providers = list(cfg.get("configured_providers") or [])
        configured_models = dict(cfg.get("configured_models") or {})
        current_provider = cfg.get("current_provider")
        current_model_val = cfg.get("current_model")

        # Remove model from the provider's model list
        provider_models = list(configured_models.get(selected) or [])
        if model in provider_models:
            provider_models.remove(model)
            
        # If no models left for this provider, remove the provider entirely
        if not provider_models:
            if selected in providers:
                providers.remove(selected)
            if selected in configured_models:
                del configured_models[selected]
            
            # If this was the current provider, switch to another provider
            if current_provider == selected:
                if providers:
                    # Switch to first available provider
                    current_provider = providers[0]
                    # Get first model for the new provider
                    new_provider_models = configured_models.get(current_provider, [])
                    current_model_val = new_provider_models[0] if new_provider_models else None
                else:
                    # No providers left
                    current_provider = None
                    current_model_val = None
        else:
            # Update the model list for this provider
            configured_models[selected] = provider_models
            
            # If the removed model was the current model, switch to another model
            if current_provider == selected and current_model_val == model:
                current_model_val = provider_models[0] if provider_models else None

        return self.create_or_update_configuration(
            workspace_id=workspace_id,
            agent_id=agent_id,
            configured_providers=providers,
            configured_models=configured_models,
            current_provider=current_provider,
            current_model=current_model_val,
            user_id=user_id,
        )

    def get_workspace_configurations(self, workspace_id: int) -> List[Dict[str, Any]]:
        doc = self._get_workspace_document(workspace_id)
        if not doc:
            return []

        configs: List[Dict[str, Any]] = []
        for key, cfg in (doc.get("agent_configs") or {}).items():
            if not cfg.get("is_active", True):
                continue
            agent_id = None if key == DEFAULT_CONFIG_KEY else int(key)
            configs.append(
                {
                    "id": f"{workspace_id}:{key}",
                    "workspace_id": workspace_id,
                    "agent_id": agent_id,
                    "configured_providers": cfg.get("configured_providers") or [],
                    "configured_models": cfg.get("configured_models") or {},
                    "current_provider": cfg.get("current_provider"),
                    "current_model": cfg.get("current_model"),
                    "created_at": cfg.get("created_at"),
                    "updated_at": cfg.get("updated_at"),
                    "created_by": cfg.get("created_by"),
                    "updated_by": cfg.get("updated_by"),
                }
            )

        configs.sort(key=lambda x: (-1 if x["agent_id"] is None else x["agent_id"]))
        return configs

    def get_current_provider(self, workspace_id: int, agent_id: Optional[int] = None) -> Optional[str]:
        config = self.get_effective_configuration(workspace_id, agent_id) if agent_id is not None else self.get_configuration(workspace_id, agent_id)
        return config.get("current_provider") if config else None

    def list_configured_providers(self, workspace_id: int, agent_id: Optional[int] = None) -> List[str]:
        config = self.get_effective_configuration(workspace_id, agent_id) if agent_id is not None else self.get_configuration(workspace_id, agent_id)
        return list(config.get("configured_providers") or []) if config else []

    def delete_configuration(
        self,
        workspace_id: int,
        agent_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        key = self._agent_key(agent_id)
        doc = self._get_workspace_document(workspace_id)
        cfg = ((doc or {}).get("agent_configs") or {}).get(key)
        if not cfg or not cfg.get("is_active", True):
            return False

        now = self._utcnow()
        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"agent_configs.{key}.is_active": False,
                    f"agent_configs.{key}.updated_at": now,
                    f"agent_configs.{key}.updated_by": user_id,
                    "updated_at": now,
                }
            },
        )
        return True

    def bulk_create_agent_configurations(
        self,
        workspace_id: int,
        agent_ids: List[int],
        configured_providers: Optional[List[str]] = None,
        current_provider: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        created = []
        if not agent_ids:
            return created

        defaults = configured_providers or ["azure"]
        active_provider = current_provider or "azure"

        # Auto-populate configured_models with the active provider's default model
        configured_models = {}
        creds = self.get_provider_credentials(workspace_id, active_provider)
        default_model = creds.get("model") if creds else None
        if default_model:
            configured_models[active_provider] = [default_model]

        for agent_id in agent_ids:
            existing = self.get_configuration(workspace_id, agent_id)
            if existing:
                continue
            created.append(
                self.create_or_update_configuration(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    configured_providers=defaults,
                    configured_models=configured_models or None,
                    current_provider=active_provider,
                    current_model=default_model,
                    user_id=user_id,
                )
            )
        return created

    def delete_workspace_configurations(self, workspace_id: int, user_id: Optional[int] = None) -> int:
        """Hard-delete the entire workspace document from llm_configs.workspace_configs."""
        result = self._get_collection().delete_one({"workspace_id": workspace_id})
        deleted = result.deleted_count
        if deleted:
            logger.info(f"Hard-deleted workspace config document for workspace_id={workspace_id}")
        return deleted

    def remove_model_from_provider(
        self,
        workspace_id: int,
        provider_name: str,
        model_name: str,
        user_id: Optional[int] = None,
    ) -> bool:
        """Remove a specific model from a provider's available_models list.

        If the removed model was the top-level 'model', update it to the first remaining model.
        """
        provider = provider_name.lower().strip()
        existing = self.get_provider_credentials(workspace_id, provider)
        if not existing:
            return False

        available_models = existing.get("available_models") or []
        updated_models = [m for m in available_models if m["model_name"] != model_name]

        if len(updated_models) == len(available_models):
            return False  # Model not found

        now = self._utcnow()

        # If the removed model was the top-level model, switch to the first remaining
        top_level_model = existing.get("model")
        new_top_model = top_level_model
        new_deployment = existing.get("deployment_name")
        if top_level_model == model_name and updated_models:
            new_top_model = updated_models[0]["model_name"]
            new_deployment = updated_models[0].get("deployment_name") or new_top_model

        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"provider_credentials.{provider}.available_models": updated_models,
                    f"provider_credentials.{provider}.model": new_top_model,
                    f"provider_credentials.{provider}.deployment_name": new_deployment,
                    f"provider_credentials.{provider}.updated_at": now,
                    f"provider_credentials.{provider}.updated_by": user_id,
                    "updated_at": now,
                },
            },
        )

        # Remove model from model_assignments (handle dots in model names)
        current_assignments = existing.get("model_assignments") or {}
        if model_name in current_assignments:
            del current_assignments[model_name]
            self._get_collection().update_one(
                {"workspace_id": workspace_id},
                {"$set": {f"provider_credentials.{provider}.model_assignments": current_assignments}},
            )

        return True

    def set_model_assignments(
        self,
        workspace_id: int,
        provider_name: str,
        model_name: str,
        agent_ids: List[int],
        user_id: Optional[int] = None,
    ) -> None:
        """Set the agent assignments for a specific model under a provider.

        This is independent per model — setting agents for model A does NOT
        affect model B's assignments.
        """
        provider = provider_name.lower().strip()
        now = self._utcnow()

        # Read the full model_assignments dict, update the key, write back
        # (avoids MongoDB dot-notation issues with model names like 'gpt-4.1')
        existing = self.get_provider_credentials(workspace_id, provider)
        current_assignments = (existing.get("model_assignments") or {}) if existing else {}
        current_assignments[model_name] = agent_ids

        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"provider_credentials.{provider}.model_assignments": current_assignments,
                    f"provider_credentials.{provider}.updated_at": now,
                    f"provider_credentials.{provider}.updated_by": user_id,
                    "updated_at": now,
                }
            },
        )

    def get_model_assignments(
        self,
        workspace_id: int,
        provider_name: str,
        model_name: str,
    ) -> List[int]:
        """Get agent IDs assigned to a specific model under a provider."""
        provider = provider_name.lower().strip()
        existing = self.get_provider_credentials(workspace_id, provider)
        if not existing:
            return []
        assignments = existing.get("model_assignments") or {}
        return assignments.get(model_name) or []

    def _ensure_model_in_provider_available_models(
        self,
        workspace_id: int,
        provider: str,
        model: str,
    ) -> None:
        """Ensure a model is in the provider's available_models list."""
        existing = self.get_provider_credentials(workspace_id, provider)
        if not existing:
            return
        
        available_models = existing.get("available_models") or []
        
        # Check if model already exists
        if any(m.get("model_name") == model for m in available_models):
            return
        
        # Add the model to available_models
        available_models.append({
            "model_name": model,
            "deployment_name": model
        })
        
        # Update the provider credentials
        now = self._utcnow()
        self._get_collection().update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    f"provider_credentials.{provider}.available_models": available_models,
                    f"provider_credentials.{provider}.updated_at": now,
                    "updated_at": now,
                }
            },
        )


llm_router_config_store = LLMRouterConfigStore()
