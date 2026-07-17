"""
SQLAlchemy ORM Models for TrustAI Integration

These models represent the auto-created tables for TrustAI integration.
Existing tables (workspace_master, agents_details, workspace_agents_mapping_2, users)
are assumed to exist and are not managed by this package.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint, UUID
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class TrustAIWorkspaceConfig(Base):
    """
    Stores TrustAI configuration for each workspace.
    Maps workspace_id to TrustAI app_id and api_key.
    """
    __tablename__ = 'trustai_workspace_config'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=False, unique=True)
    x_app_id = Column(String(255), nullable=False)
    x_api_key = Column(Text, nullable=False)
    api_endpoint = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TrustAIWorkspaceConfig(workspace_id={self.workspace_id}, x_app_id={self.x_app_id})>"


class ProviderModel(Base):
    """
    Stores available provider-model mappings for TrustAI.
    Each row represents a model configuration with its TrustAI model key.
    """
    __tablename__ = 'provider_models'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_name = Column(String(100), nullable=False)
    deployment_name = Column(String(200), nullable=False)
    trustai_model_key = Column(String(255), nullable=False, unique=True)
    is_system_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('provider_name', 'deployment_name', name='uq_provider_deployment'),
    )

    def __repr__(self):
        return (
            f"<ProviderModel(provider={self.provider_name}, "
            f"model={self.deployment_name}, key={self.trustai_model_key})>"
        )


class WorkspaceAgentProviderModelMapping(Base):
    """
    Maps workspace + agent to available provider models.
    Defines which models are configured for each agent in a workspace.
    """
    __tablename__ = 'workspace_agent_provider_model_mapping'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=False)
    agent_id = Column(BigInteger, nullable=False)
    provider_model_id = Column(
        BigInteger,
        ForeignKey('provider_models.id'),
        nullable=False
    )
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger)
    updated_by = Column(BigInteger)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationship
    provider_model = relationship("ProviderModel")

    __table_args__ = (
        UniqueConstraint(
            'workspace_id', 'agent_id', 'provider_model_id',
            name='uq_workspace_agent_provider_model'
        ),
    )

    def __repr__(self):
        return (
            f"<WorkspaceAgentProviderModelMapping("
            f"workspace_id={self.workspace_id}, agent_id={self.agent_id}, "
            f"provider_model_id={self.provider_model_id})>"
        )


class UserAgentProviderModelPreference(Base):
    """
    Stores user-specific model preferences for agents.
    Overrides workspace-level defaults for specific users.
    """
    __tablename__ = 'user_agent_provider_model_preference'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    agent_id = Column(BigInteger, nullable=False)
    provider_model_id = Column(
        BigInteger,
        ForeignKey('provider_models.id'),
        nullable=False
    )
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationship
    provider_model = relationship("ProviderModel")

    __table_args__ = (
        UniqueConstraint(
            'workspace_id', 'user_id', 'agent_id',
            name='uq_workspace_user_agent'
        ),
    )

    def __repr__(self):
        return (
            f"<UserAgentProviderModelPreference("
            f"workspace_id={self.workspace_id}, user_id={self.user_id}, "
            f"agent_id={self.agent_id}, provider_model_id={self.provider_model_id})>"
        )
