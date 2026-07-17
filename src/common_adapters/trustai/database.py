"""
Database Management for TrustAI Integration

Handles database connection, initialization, and ORM operations.
Auto-creates TrustAI tables if they don't exist.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager

from .models import (
    Base,
    TrustAIWorkspaceConfig,
    ProviderModel,
    WorkspaceAgentProviderModelMapping,
    UserAgentProviderModelPreference
)

logger = logging.getLogger(__name__)


class TrustAIDatabaseManager:
    """
    Manages database connections and ORM operations for TrustAI integration.

    Features:
    - Auto-creates tables if they don't exist
    - Provides session management
    - Handles connection pooling
    - Thread-safe operations
    """

    def __init__(self, database_url: str):
        """
        Initialize database manager.

        Args:
            database_url: PostgreSQL connection string
                Format: postgresql://user:password@host:port/dbname
        """
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()

    def _initialize_engine(self):
        """Initialize SQLAlchemy engine and session factory."""
        try:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,  # Verify connections before using
                pool_size=10,  # Connection pool size
                max_overflow=20,  # Max overflow connections
                echo=False  # Set to True for SQL logging
            )
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            logger.info("Database engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise

    def initialize_tables(self):
        """
        Create TrustAI tables if they don't exist.

        Creates:
        - trustai_workspace_config
        - provider_models
        - workspace_agent_provider_model_mapping
        - user_agent_provider_model_preference
        """
        try:
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()

            tables_to_create = [
                'trustai_workspace_config',
                'provider_models',
                'workspace_agent_provider_model_mapping',
                'user_agent_provider_model_preference'
            ]

            missing_tables = [t for t in tables_to_create if t not in existing_tables]

            if missing_tables:
                logger.info(f"Creating missing tables: {missing_tables}")
                Base.metadata.create_all(bind=self.engine)
                logger.info("All TrustAI tables created successfully")
            else:
                logger.info("All TrustAI tables already exist")

        except Exception as e:
            logger.error(f"Error initializing tables: {e}")
            raise

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions.

        Usage:
            with db_manager.get_session() as session:
                # Perform database operations
                result = session.query(Model).all()

        Yields:
            Session: SQLAlchemy session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def get_workspace_config(self, workspace_id: str) -> Optional[TrustAIWorkspaceConfig]:
        """
        Get TrustAI configuration for a workspace.

        Args:
            workspace_id: UUID string of the workspace

        Returns:
            TrustAIWorkspaceConfig or None if not found
        """
        with self.get_session() as session:
            return session.query(TrustAIWorkspaceConfig).filter_by(
                workspace_id=workspace_id
            ).first()

    def save_workspace_config(
        self,
        workspace_id: str,
        x_app_id: str,
        x_api_key: str,
        api_endpoint: str
    ) -> TrustAIWorkspaceConfig:
        """
        Save or update TrustAI workspace configuration.

        Args:
            workspace_id: UUID string of the workspace
            x_app_id: TrustAI application ID
            x_api_key: TrustAI API key
            api_endpoint: TrustAI API endpoint URL

        Returns:
            Saved TrustAIWorkspaceConfig instance
        """
        with self.get_session() as session:
            # Check if config exists
            config = session.query(TrustAIWorkspaceConfig).filter_by(
                workspace_id=workspace_id
            ).first()

            if config:
                # Update existing
                config.x_app_id = x_app_id
                config.x_api_key = x_api_key
                config.api_endpoint = api_endpoint
                logger.info(f"Updated workspace config for workspace_id={workspace_id}")
            else:
                # Create new
                config = TrustAIWorkspaceConfig(
                    workspace_id=workspace_id,
                    x_app_id=x_app_id,
                    x_api_key=x_api_key,
                    api_endpoint=api_endpoint
                )
                session.add(config)
                logger.info(f"Created new workspace config for workspace_id={workspace_id}")

            session.flush()
            session.refresh(config)
            return config

    def get_system_default_provider_model(self) -> Optional[ProviderModel]:
        """
        Get the system default provider model.

        Returns:
            ProviderModel marked as is_system_default=True
        """
        with self.get_session() as session:
            return session.query(ProviderModel).filter_by(
                is_system_default=True,
                is_active=True
            ).first()

    def get_provider_model(
        self,
        provider_name: str,
        deployment_name: str
    ) -> Optional[ProviderModel]:
        """
        Get a provider model by provider and deployment name.

        Args:
            provider_name: Provider name (e.g., "azure", "openai")
            deployment_name: Model deployment name (e.g., "gpt-4-1")

        Returns:
            ProviderModel or None
        """
        with self.get_session() as session:
            return session.query(ProviderModel).filter_by(
                provider_name=provider_name,
                deployment_name=deployment_name,
                is_active=True
            ).first()

    def create_provider_model(
        self,
        provider_name: str,
        deployment_name: str,
        trustai_model_key: str,
        is_system_default: bool = False
    ) -> ProviderModel:
        """
        Create a new provider model configuration.

        Args:
            provider_name: Provider name
            deployment_name: Model deployment name
            trustai_model_key: TrustAI model key
            is_system_default: Whether this is the system default

        Returns:
            Created ProviderModel
        """
        with self.get_session() as session:
            model = ProviderModel(
                provider_name=provider_name,
                deployment_name=deployment_name,
                trustai_model_key=trustai_model_key,
                is_system_default=is_system_default,
                is_active=True
            )
            session.add(model)
            session.flush()
            session.refresh(model)
            logger.info(
                f"Created provider model: {provider_name}/{deployment_name} -> {trustai_model_key}"
            )
            return model

    def get_workspace_agent_default_model(
        self,
        workspace_id: str,
        agent_id: int
    ) -> Optional[ProviderModel]:
        """
        Get the default provider model for a workspace + agent combination.

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID

        Returns:
            Default ProviderModel or None
        """
        with self.get_session() as session:
            mapping = session.query(WorkspaceAgentProviderModelMapping).filter_by(
                workspace_id=workspace_id,
                agent_id=agent_id,
                is_default=True,
                is_active=True
            ).first()

            return mapping.provider_model if mapping else None

    def set_workspace_agent_default_model(
        self,
        workspace_id: str,
        agent_id: int,
        provider_model_id: int,
        created_by: Optional[int] = None
    ) -> WorkspaceAgentProviderModelMapping:
        """
        Set the default provider model for a workspace + agent.

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID
            provider_model_id: Provider model ID
            created_by: User ID who created this mapping

        Returns:
            Created or updated mapping
        """
        with self.get_session() as session:
            # Clear existing defaults for this workspace + agent
            session.query(WorkspaceAgentProviderModelMapping).filter_by(
                workspace_id=workspace_id,
                agent_id=agent_id,
                is_default=True
            ).update({'is_default': False})

            # Check if mapping exists
            mapping = session.query(WorkspaceAgentProviderModelMapping).filter_by(
                workspace_id=workspace_id,
                agent_id=agent_id,
                provider_model_id=provider_model_id
            ).first()

            if mapping:
                mapping.is_default = True
                mapping.is_active = True
                mapping.updated_by = created_by
            else:
                mapping = WorkspaceAgentProviderModelMapping(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    provider_model_id=provider_model_id,
                    is_default=True,
                    is_active=True,
                    created_by=created_by
                )
                session.add(mapping)

            session.flush()
            session.refresh(mapping)
            logger.info(
                f"Set default model for workspace={workspace_id}, "
                f"agent={agent_id}, provider_model={provider_model_id}"
            )
            return mapping

    def get_user_agent_preference(
        self,
        workspace_id: str,
        user_id: int,
        agent_id: int
    ) -> Optional[ProviderModel]:
        """
        Get user-specific provider model preference.

        Args:
            workspace_id: UUID string of the workspace
            user_id: User ID
            agent_id: Agent ID

        Returns:
            User's preferred ProviderModel or None
        """
        with self.get_session() as session:
            pref = session.query(UserAgentProviderModelPreference).filter_by(
                workspace_id=workspace_id,
                user_id=user_id,
                agent_id=agent_id
            ).first()

            return pref.provider_model if pref else None

    def set_user_agent_preference(
        self,
        workspace_id: str,
        user_id: int,
        agent_id: int,
        provider_model_id: int
    ) -> UserAgentProviderModelPreference:
        """
        Set user-specific provider model preference.

        Args:
            workspace_id: UUID string of the workspace
            user_id: User ID
            agent_id: Agent ID
            provider_model_id: Provider model ID

        Returns:
            Created or updated preference
        """
        with self.get_session() as session:
            pref = session.query(UserAgentProviderModelPreference).filter_by(
                workspace_id=workspace_id,
                user_id=user_id,
                agent_id=agent_id
            ).first()

            if pref:
                pref.provider_model_id = provider_model_id
            else:
                pref = UserAgentProviderModelPreference(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    provider_model_id=provider_model_id
                )
                session.add(pref)

            session.flush()
            session.refresh(pref)
            logger.info(
                f"Set user preference: workspace={workspace_id}, user={user_id}, "
                f"agent={agent_id}, provider_model={provider_model_id}"
            )
            return pref

    def resolve_provider_model(
        self,
        workspace_id: str,
        agent_id: int,
        user_id: Optional[int] = None
    ) -> Optional[ProviderModel]:
        """
        Resolve the provider model using the hierarchy:
        1. User-specific preference
        2. Workspace-agent default
        3. System default

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID
            user_id: User ID (optional)

        Returns:
            Resolved ProviderModel or None
        """
        # 1. Check user preference
        if user_id:
            user_model = self.get_user_agent_preference(workspace_id, user_id, agent_id)
            if user_model:
                logger.debug(f"Resolved model from user preference: {user_model}")
                return user_model

        # 2. Check workspace-agent default
        workspace_model = self.get_workspace_agent_default_model(workspace_id, agent_id)
        if workspace_model:
            logger.debug(f"Resolved model from workspace-agent default: {workspace_model}")
            return workspace_model

        # 3. Fallback to system default
        system_model = self.get_system_default_provider_model()
        if system_model:
            logger.debug(f"Resolved model from system default: {system_model}")
            return system_model

        logger.warning(
            f"No provider model resolved for workspace={workspace_id}, "
            f"agent={agent_id}, user={user_id}"
        )
        return None

    def list_workspace_agent_models(
        self,
        workspace_id: str,
        agent_id: int
    ) -> List[Dict[str, Any]]:
        """
        List all available provider models for a workspace + agent.

        Args:
            workspace_id: UUID string of the workspace
            agent_id: Agent ID

        Returns:
            List of dicts with provider model information
        """
        with self.get_session() as session:
            mappings = session.query(WorkspaceAgentProviderModelMapping).filter_by(
                workspace_id=workspace_id,
                agent_id=agent_id,
                is_active=True
            ).all()

            return [
                {
                    'provider_name': m.provider_model.provider_name,
                    'deployment_name': m.provider_model.deployment_name,
                    'is_default': m.is_default,
                    'provider_model_id': m.provider_model_id
                }
                for m in mappings
            ]

    def close(self):
        """Close database engine and cleanup resources."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database engine closed")
