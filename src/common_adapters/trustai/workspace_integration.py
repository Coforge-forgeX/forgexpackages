"""
TrustAI Workspace Integration

Handles workspace registration, API key generation, and configuration management.
"""

import logging
from typing import Dict, Any, Optional, Tuple
import httpx

from .database import TrustAIDatabaseManager
from .endpoints import TrustAIEndpoints, TrustAIEnvVars

logger = logging.getLogger(__name__)


class TrustAIWorkspaceIntegration:
    """
    Manages TrustAI workspace integration operations.

    Features:
    - Register workspace with TrustAI
    - Generate and manage API keys
    - Configure workspace-level settings
    - Manage agent-level provider model mappings
    """

    def __init__(self, db_manager: TrustAIDatabaseManager):
        """
        Initialize workspace integration.

        Args:
            db_manager: TrustAIDatabaseManager instance
        """
        self.db = db_manager
        self.endpoints = TrustAIEndpoints
        self.master_api_key = TrustAIEnvVars.get_master_api_key()

    async def register_workspace(
        self,
        workspace_id: str,
        trustai_config: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Register workspace with TrustAI and store configuration.

        This method:
        1. Registers the app with TrustAI
        2. Generates an API key for the app
        3. Stores the configuration in the database
        4. Initializes default agent configurations

        Args:
            workspace_id: UUID string of the workspace
            trustai_config: TrustAI configuration dict containing:
                - application: App details (name, description, etc.)
                - guardrails: List of guardrail types
                - system_config: System configuration

        Returns:
            Tuple of (app_id, api_key)

        Raises:
            httpx.HTTPError: If API calls fail
            ValueError: If configuration is invalid
        """
        try:
            # Step 1: Register app with TrustAI
            logger.info(f"Registering workspace {workspace_id} with TrustAI")
            app_id = await self._register_app(trustai_config)
            logger.info(f"App registered successfully. app_id={app_id}")

            # Step 2: Generate API key using app_id
            api_key = await self._generate_api_key(app_id)
            logger.info(f"API key generated successfully for app_id={app_id}")

            # Step 3: Store configuration in database
            self.db.save_workspace_config(
                workspace_id=workspace_id,
                x_app_id=app_id,
                x_api_key=api_key,
                api_endpoint=self.endpoints.CHAT_COMPLETIONS
            )
            logger.info(f"Workspace config saved to database for workspace_id={workspace_id}")

            # Step 4: Initialize default agent configurations
            await self._initialize_default_agent_configs(workspace_id)

            return app_id, api_key

        except Exception as e:
            logger.error(f"Failed to register workspace {workspace_id}: {e}")
            raise

    async def _register_app(self, trustai_config: Dict[str, Any]) -> str:
        """
        Register application with TrustAI.

        Args:
            trustai_config: Configuration dict

        Returns:
            Application ID (UUID string)
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.endpoints.REGISTER_APP,
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Api-Key": self.master_api_key
                },
                json=trustai_config
            )
            response.raise_for_status()
            data = response.json()

            # Extract app_id from response
            app_id = data.get('app_id') or data.get('application_id') or data.get('id')
            if not app_id:
                raise ValueError(f"No app_id found in response: {data}")

            return str(app_id)

    async def _generate_api_key(self, app_id: str) -> str:
        """
        Generate API key for the registered app.

        Args:
            app_id: Application ID (used as user_id)

        Returns:
            Generated API key
        """
        lifetime_days = TrustAIEnvVars.get_api_key_lifetime()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.endpoints.GENERATE_API_KEY,
                headers={
                    "accept": "application/json",
                    "X-API-KEY": self.master_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "user_id": app_id,
                    "lifetime_days": lifetime_days
                }
            )
            response.raise_for_status()
            data = response.json()

            # Extract API key from response
            api_key = data.get('api_key') or data.get('key')
            if not api_key:
                raise ValueError(f"No api_key found in response: {data}")

            return str(api_key)

    async def _initialize_default_agent_configs(self, workspace_id: str):
        """
        Initialize default agent configurations for the workspace.

        Uses the system default provider model to set up initial configs.

        Args:
            workspace_id: UUID string of the workspace
        """
        system_default = self.db.get_system_default_provider_model()
        if not system_default:
            logger.warning(
                f"No system default provider model found. "
                f"Skipping default agent config initialization for workspace {workspace_id}"
            )
            return

        logger.info(
            f"Initialized default agent configs for workspace {workspace_id} "
            f"using system default: {system_default.provider_name}/{system_default.deployment_name}"
        )

    async def list_api_keys(self, workspace_id: str) -> list:
        """
        List all API keys for a workspace.

        Args:
            workspace_id: UUID string of the workspace

        Returns:
            List of API key information dicts
        """
        workspace_config = self.db.get_workspace_config(workspace_id)
        if not workspace_config:
            raise ValueError(f"No TrustAI config found for workspace {workspace_id}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.endpoints.LIST_API_KEYS}?user_id={workspace_config.x_app_id}",
                headers={
                    "accept": "application/json",
                    "X-API-KEY": self.master_api_key
                }
            )
            response.raise_for_status()
            return response.json()

    async def renew_api_key(self, workspace_id: str) -> str:
        """
        Generate a new API key for the workspace.

        Args:
            workspace_id: UUID string of the workspace

        Returns:
            New API key
        """
        workspace_config = self.db.get_workspace_config(workspace_id)
        if not workspace_config:
            raise ValueError(f"No TrustAI config found for workspace {workspace_id}")

        # Generate new API key
        new_api_key = await self._generate_api_key(workspace_config.x_app_id)

        # Update in database
        self.db.save_workspace_config(
            workspace_id=workspace_id,
            x_app_id=workspace_config.x_app_id,
            x_api_key=new_api_key,
            api_endpoint=workspace_config.api_endpoint
        )

        logger.info(f"API key renewed for workspace {workspace_id}")
        return new_api_key

    def configure_agent_provider_model(
        self,
        workspace_id: str,
        agent_id: int,
        provider_name: str,
        deployment_name: str,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Configure provider model for a workspace + agent.

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID
            provider_name: Provider name (e.g., "azure")
            deployment_name: Model deployment name (e.g., "gpt-4-1")
            created_by: User ID who created this config

        Returns:
            Configuration details dict
        """
        # Get or create provider model
        provider_model = self.db.get_provider_model(provider_name, deployment_name)
        if not provider_model:
            raise ValueError(
                f"Provider model not found: {provider_name}/{deployment_name}. "
                "Please add this model to the provider_models table first."
            )

        # Set as default for this workspace + agent
        mapping = self.db.set_workspace_agent_default_model(
            workspace_id=workspace_id,
            agent_id=agent_id,
            provider_model_id=provider_model.id,
            created_by=created_by
        )

        logger.info(
            f"Configured agent provider model: workspace={workspace_id}, "
            f"agent={agent_id}, provider={provider_name}, model={deployment_name}"
        )

        return {
            'workspace_id': workspace_id,
            'agent_id': agent_id,
            'provider_name': provider_model.provider_name,
            'deployment_name': provider_model.deployment_name,
            'trustai_model_key': provider_model.trustai_model_key,
            'is_default': mapping.is_default
        }

    def configure_user_specific_agent_provider_model(
        self,
        workspace_id: str,
        user_id: int,
        agent_id: int,
        provider_name: str,
        deployment_name: str
    ) -> Dict[str, Any]:
        """
        Configure user-specific provider model preference.

        Args:
            workspace_id: UUID string of the workspace
            user_id: User ID
            agent_id: Agent ID
            provider_name: Provider name
            deployment_name: Model deployment name

        Returns:
            Configuration details dict
        """
        # Get provider model
        provider_model = self.db.get_provider_model(provider_name, deployment_name)
        if not provider_model:
            raise ValueError(
                f"Provider model not found: {provider_name}/{deployment_name}. "
                "Please add this model to the provider_models table first."
            )

        # Set user preference
        self.db.set_user_agent_preference(
            workspace_id=workspace_id,
            user_id=user_id,
            agent_id=agent_id,
            provider_model_id=provider_model.id
        )

        logger.info(
            f"Configured user-specific provider model: workspace={workspace_id}, "
            f"user={user_id}, agent={agent_id}, provider={provider_name}, model={deployment_name}"
        )

        return {
            'workspace_id': workspace_id,
            'user_id': user_id,
            'agent_id': agent_id,
            'provider_name': provider_model.provider_name,
            'deployment_name': provider_model.deployment_name,
            'trustai_model_key': provider_model.trustai_model_key
        }

    def fetch_workspace_agent_provider_model(
        self,
        workspace_id: str,
        agent_id: int,
        user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch the resolved provider model for a workspace + agent + user.

        Uses the hierarchy:
        1. User-specific preference
        2. Workspace-agent default
        3. System default

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID
            user_id: User ID (optional)

        Returns:
            Provider model details dict or None
        """
        provider_model = self.db.resolve_provider_model(
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id
        )

        if not provider_model:
            return None

        return {
            'provider_name': provider_model.provider_name,
            'deployment_name': provider_model.deployment_name,
            'trustai_model_key': provider_model.trustai_model_key,
            'is_system_default': provider_model.is_system_default
        }

    def fetch_workspace_provider_model_details(
        self,
        workspace_id: str,
        agent_id: int
    ) -> Dict[str, Any]:
        """
        Fetch all available provider models for a workspace + agent.

        Returns both available providers and agent-specific listings.
        Does NOT include trustai_model_key (confidential).

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID

        Returns:
            Dict with available providers and agent listings
        """
        models = self.db.list_workspace_agent_models(workspace_id, agent_id)

        return {
            'workspace_id': workspace_id,
            'agent_id': agent_id,
            'available_models': [
                {
                    'provider': m['provider_name'],
                    'model': m['deployment_name'],
                    'is_default': m['is_default']
                }
                for m in models
            ]
        }
