"""
TrustAI Workspace Integration

Handles workspace registration, API key generation, and configuration management.
"""

import logging
from typing import Dict, Any, Optional
import httpx

from .database import TrustAIDatabaseManager
from .endpoints import TrustAIEndpoints
from .config import TrustAIEnvVars

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
        
    @property
    def trustai_master_key(self):
        """
        Get trustai master key.
        """
        
        return TrustAIEnvVars.get_master_api_key()

    async def register_workspace(
        self,
        workspace_id: str,
        trustai_config: Dict[str, Any],
        agent_ids: list = None,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        Register workspace with TrustAI and store configuration.

        This method:
        1. Registers the app with TrustAI
        2. Generates an API key for the app
        3. Stores the configuration in the database
        4. Initializes default agent configurations

        Args:
            workspace_id: Int string of the workspace
            trustai_config: TrustAI configuration dict containing:
                - application: App details (name, description, etc.)
                - guardrails: List of guardrail types
                - system_config: System configuration
            agent_ids: List of agent IDs from response (optional)
            user_id: User ID who registered workspace (optional)

        Returns:
            Dict containing:
                - app_id: TrustAI application ID
                - api_key: Generated API key
                - agent_ids: List of agent IDs (if provided)
                - user_id: User ID (if provided)

        Raises:
            httpx.HTTPError: If API calls fail
            ValueError: If configuration is invalid
        """
        try:
            # Step 1: Register app with TrustAI
            logger.info(f"Registering workspace {workspace_id} with TrustAI")
            
            # check if name is string(must be string to avoid 422)
            if not isinstance(trustai_config['application']['name'],str):
                trustai_config['application']['name'] = str(trustai_config['application']['name'])
                
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
            await self._initialize_default_agent_configs(
                workspace_id=workspace_id,
                agent_ids=agent_ids,
                created_by=user_id
            )

            return {
                'app_id': app_id,
                'api_key': api_key,
                'agent_ids': agent_ids,
                'user_id': user_id
            }

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
                    "X-Api-Key": self.trustai_master_key
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
                    "X-API-KEY": self.trustai_master_key,
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

    async def _initialize_default_agent_configs(
        self,
        workspace_id: str,
        agent_ids: list = None,
        created_by: int = None
    ):
        """
        Initialize default agent configurations for the workspace.

        Creates default provider model from .env if needed.
        Configures each agent with system default model.

        Args:
            workspace_id: UUID string of workspace
            agent_ids: List of agent IDs to configure (if None, skip)
            created_by: User ID who created configs
        """
        # Ensure default model exists (create from .env if needed)
        system_default = self.db.ensure_default_provider_model()
        logger.info(f"system default {system_default}")
        if not agent_ids:
            logger.warning(
                f"No agent_ids provided. "
                f"Skipping agent config initialization for workspace {workspace_id}"
            )
            return

        logger.info(
            f"Initializing configs for {len(agent_ids)} agents in workspace {workspace_id} "
            f"using system default: {system_default['provider_name']}/{system_default['deployment_name']}"
        )
        if not system_default:
            logger.error(
                        f"Initializing configs failed for  {len(agent_ids)} agents in workspace {workspace_id} "
                        f"due to missing system default in provider model table"
                    )
            raise ValueError("System Default configuration not found in provider model")
        # Configure each agent
        success_count = 0
        for agent_id in agent_ids:
            try:
                self.configure_agent_provider_model(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    provider_name=system_default['provider_name'],
                    deployment_name=system_default['deployment_name'],
                    created_by=created_by
                )
                success_count += 1
                logger.info(f"Configured agent {agent_id} with default model")
            except Exception as e:
                import traceback
                logger.error(f"Failed to configure agent {agent_id}\n{traceback.format_exc()}")
                logger.error(f"Failed to configure agent {agent_id}: {e}")

        logger.info(
            f"Initialized {success_count}/{len(agent_ids)} agent configs for workspace {workspace_id}"
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

        # Extract attr before detached
        app_id = workspace_config.x_app_id
        api_key = workspace_config.x_api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.endpoints.LIST_API_KEYS}?user_id={app_id}",
                headers={
                    "accept": "application/json",
                    "X-API-KEY": api_key
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

        # Extract attrs before detached
        app_id = workspace_config.x_app_id
        api_endpoint = workspace_config.api_endpoint

        # Generate new API key
        new_api_key = await self._generate_api_key(app_id)

        # Update in database
        self.db.save_workspace_config(
            workspace_id=workspace_id,
            x_app_id=app_id,
            x_api_key=new_api_key,
            api_endpoint=api_endpoint
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
        # Get provider model and extract attrs immediately
        provider_model = self.db.get_provider_model(provider_name, deployment_name)
        if not provider_model:
            raise ValueError(
                f"Provider model not found: {provider_name}/{deployment_name}. "
                "Please add this model to the provider_models table first."
            )

        # # Extract attrs before obj becomes detached
        # provider_model_id = provider_model.id
        # model_provider_name = provider_model.provider_name
        # model_deployment_name = provider_model.deployment_name
        # model_trustai_key = provider_model.trustai_model_key
        provider_model_id = provider_model["id"]
        model_provider_name = provider_model["provider_name"]
        model_deployment_name = provider_model["deployment_name"]
        model_trustai_key = provider_model["trustai_model_key"]
        # Set as default for this workspace + agent
        mapping = self.db.set_workspace_agent_default_model(
            workspace_id=workspace_id,
            agent_id=agent_id,
            provider_model_id=provider_model_id,
            created_by=created_by
        )

        # Extract mapping attrs immediately
        is_default = mapping["is_default"]

        logger.info(
            f"Configured agent provider model: workspace={workspace_id}, "
            f"agent={agent_id}, provider={provider_name}, model={deployment_name}"
        )

        return {
            'workspace_id': workspace_id,
            'agent_id': agent_id,
            'provider_name': model_provider_name,
            'deployment_name': model_deployment_name,
            'trustai_model_key': model_trustai_key,
            'is_default': is_default
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
        # Get provider model and extract attrs immediately
        provider_model = self.db.get_provider_model(provider_name, deployment_name)
        if not provider_model:
            raise ValueError(
                f"Provider model not found: {provider_name}/{deployment_name}. "
                "Please add this model to the provider_models table first."
            )

        # Extract from dict
        provider_model_id = provider_model["id"]
        model_provider_name = provider_model["provider_name"]
        model_deployment_name = provider_model["deployment_name"]
        model_trustai_key = provider_model["trustai_model_key"]

        # Set user preference
        self.db.set_user_agent_preference(
            workspace_id=workspace_id,
            user_id=user_id,
            agent_id=agent_id,
            provider_model_id=provider_model_id
        )

        logger.info(
            f"Configured user-specific provider model: workspace={workspace_id}, "
            f"user={user_id}, agent={agent_id}, provider={provider_name}, model={deployment_name}"
        )

        return {
            'workspace_id': workspace_id,
            'user_id': user_id,
            'agent_id': agent_id,
            'provider_name': model_provider_name,
            'deployment_name': model_deployment_name,
            'trustai_model_key': model_trustai_key
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

        # Extract attrs immediately before detached
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

    def get_provider_configuration(
        self,
        workspace_id: str,
        agent_id: int,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get complete provider configuration for initializing TrustAI provider.

        This method decouples the provider from the database by fetching
        all necessary credentials and configuration in one call.

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID
            user_id: User ID (optional, for model resolution)

        Returns:
            Dict containing:
                - workspace_config: Dict with x_app_id, x_api_key, api_endpoint
                - provider_model: Dict with provider_name, deployment_name, trustai_model_key
                - workspace_id: Original workspace ID
                - agent_id: Original agent ID
                - user_id: Original user ID (if provided)

        Raises:
            ValueError: If workspace config or provider model not found
        """
        # Fetch workspace configuration and extract attrs
        workspace_config = self.db.get_workspace_config(workspace_id)
        if not workspace_config:
            raise ValueError(
                f"No TrustAI configuration found for workspace {workspace_id}. "
                "Please register the workspace first."
            )

        # Extract workspace config attrs before detached
        ws_app_id = workspace_config.x_app_id
        ws_api_key = workspace_config.x_api_key
        ws_endpoint = workspace_config.api_endpoint

        # Resolve provider model (3-tier hierarchy)
        provider_model = self.db.resolve_provider_model(
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id
        )
        if not provider_model:
            raise ValueError(
                f"No provider model found for workspace={workspace_id}, "
                f"agent={agent_id}, user={user_id}. "
                "Please configure a provider model first."
            )

        # Extract provider model attrs before detached
        pm_provider_name = provider_model.provider_name
        pm_deployment_name = provider_model.deployment_name
        pm_trustai_key = provider_model.trustai_model_key
        pm_is_default = provider_model.is_system_default

        logger.info(
            f"Fetched provider configuration | workspace={workspace_id} | "
            f"agent={agent_id} | user={user_id} | "
            f"provider={pm_provider_name} | "
            f"model={pm_deployment_name}"
        )

        return {
            'workspace_config': {
                'x_app_id': ws_app_id,
                'x_api_key': ws_api_key,
                'api_endpoint': ws_endpoint
            },
            'provider_model': {
                'provider_name': pm_provider_name,
                'deployment_name': pm_deployment_name,
                'trustai_model_key': pm_trustai_key,
                'is_system_default': pm_is_default
            },
            'workspace_id': workspace_id,
            'agent_id': agent_id,
            'user_id': user_id
        }

    async def add_agents_to_workspace(
        self,
        workspace_id: str,
        agent_ids: list,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Add new agents to an existing workspace.

        Configures each new agent with the system default provider model.

        Args:
            workspace_id: UUID string of the workspace
            agent_ids: List of agent IDs to add
            created_by: User ID who is adding the agents

        Returns:
            Dict containing:
                - workspace_id: Workspace ID
                - added_agents: List of successfully added agent IDs
                - failed_agents: List of agent IDs that failed with error messages

        Raises:
            ValueError: If workspace is not registered
        """
        # Verify workspace exists
        workspace_config = self.db.get_workspace_config(workspace_id)
        if not workspace_config:
            raise ValueError(
                f"No TrustAI configuration found for workspace {workspace_id}. "
                "Please register the workspace first."
            )

        logger.info(f"Adding {len(agent_ids)} agents to workspace {workspace_id}")

        # Initialize agents with default configuration
        await self._initialize_default_agent_configs(
            workspace_id=workspace_id,
            agent_ids=agent_ids,
            created_by=created_by
        )

        # Get system default for reporting
        system_default = self.db.ensure_default_provider_model()

        # Track results
        added_agents = []
        failed_agents = []

        for agent_id in agent_ids:
            try:
                # Verify agent was configured
                config = self.db.get_workspace_agent_default_model(workspace_id, agent_id)
                if config:
                    added_agents.append(agent_id)
                    logger.info(f"Successfully added agent {agent_id} to workspace {workspace_id}")
                else:
                    failed_agents.append({
                        'agent_id': agent_id,
                        'error': 'Configuration not found after initialization'
                    })
            except Exception as e:
                failed_agents.append({
                    'agent_id': agent_id,
                    'error': str(e)
                })
                logger.error(f"Failed to verify agent {agent_id}: {e}")

        result = {
            'workspace_id': workspace_id,
            'added_agents': added_agents,
            'failed_agents': failed_agents,
            'default_model': f"{system_default['provider_name']}/{system_default['deployment_name']}"
        }

        logger.info(
            f"Agent addition complete: {len(added_agents)} succeeded, "
            f"{len(failed_agents)} failed for workspace {workspace_id}"
        )

        return result

    def remove_agents_from_workspace(
        self,
        workspace_id: str,
        agent_ids: list
    ) -> Dict[str, Any]:
        """
        Remove agents from a workspace.

        This will:
        1. Deactivate workspace-agent default model mappings
        2. Remove user-specific preferences for these agents

        Args:
            workspace_id: UUID string of the workspace
            agent_ids: List of agent IDs to remove

        Returns:
            Dict containing:
                - workspace_id: Workspace ID
                - removed_agents: List of successfully removed agent IDs
                - failed_agents: List of agent IDs that failed with error messages
        """
        logger.info(f"Removing {len(agent_ids)} agents from workspace {workspace_id}")

        removed_agents = []
        failed_agents = []

        for agent_id in agent_ids:
            try:
                # Deactivate workspace-agent mapping
                self.db.deactivate_workspace_agent_mapping(workspace_id, agent_id)

                # Remove user preferences for this agent
                self.db.remove_user_agent_preferences(workspace_id, agent_id)

                removed_agents.append(agent_id)
                logger.info(f"Successfully removed agent {agent_id} from workspace {workspace_id}")

            except Exception as e:
                failed_agents.append({
                    'agent_id': agent_id,
                    'error': str(e)
                })
                logger.error(f"Failed to remove agent {agent_id}: {e}")

        result = {
            'workspace_id': workspace_id,
            'removed_agents': removed_agents,
            'failed_agents': failed_agents
        }

        logger.info(
            f"Agent removal complete: {len(removed_agents)} succeeded, "
            f"{len(failed_agents)} failed for workspace {workspace_id}"
        )

        return result

    async def update_workspace_agents(
        self,
        workspace_id: str,
        current_agent_ids: list,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Sync workspace agents with the current list.

        Detects and handles:
        - New agents (not in workspace) -> add them
        - Deleted agents (in workspace but not in current list) -> remove them

        Args:
            workspace_id: UUID string of the workspace
            current_agent_ids: Current list of agent IDs that should exist
            created_by: User ID performing the update

        Returns:
            Dict containing:
                - workspace_id: Workspace ID
                - agents_added: List of newly added agent IDs
                - agents_removed: List of removed agent IDs
                - agents_unchanged: List of agent IDs that already existed
                - failed_operations: List of failed operations with errors
        """
        logger.info(f"Syncing agents for workspace {workspace_id}")

        # Get existing agents in workspace
        existing_agents = self.db.get_workspace_agent_ids(workspace_id)

        # Calculate differences
        current_set = set(current_agent_ids)
        existing_set = set(existing_agents)

        agents_to_add = list(current_set - existing_set)
        agents_to_remove = list(existing_set - current_set)
        agents_unchanged = list(current_set & existing_set)

        logger.info(
            f"Workspace {workspace_id} sync: "
            f"{len(agents_to_add)} to add, "
            f"{len(agents_to_remove)} to remove, "
            f"{len(agents_unchanged)} unchanged"
        )

        result = {
            'workspace_id': workspace_id,
            'agents_added': [],
            'agents_removed': [],
            'agents_unchanged': agents_unchanged,
            'failed_operations': []
        }

        # Add new agents
        if agents_to_add:
            add_result = await self.add_agents_to_workspace(
                workspace_id=workspace_id,
                agent_ids=agents_to_add,
                created_by=created_by
            )
            result['agents_added'] = add_result['added_agents']
            result['failed_operations'].extend([
                {'operation': 'add', **failed}
                for failed in add_result['failed_agents']
            ])

        # Remove deleted agents
        if agents_to_remove:
            remove_result = self.remove_agents_from_workspace(
                workspace_id=workspace_id,
                agent_ids=agents_to_remove
            )
            result['agents_removed'] = remove_result['removed_agents']
            result['failed_operations'].extend([
                {'operation': 'remove', **failed}
                for failed in remove_result['failed_agents']
            ])

        logger.info(
            f"Workspace {workspace_id} sync complete: "
            f"{len(result['agents_added'])} added, "
            f"{len(result['agents_removed'])} removed, "
            f"{len(result['failed_operations'])} failed"
        )

        return result
