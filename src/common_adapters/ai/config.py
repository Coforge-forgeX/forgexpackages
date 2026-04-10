from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional


def _require(env_name: str) -> str:
    v = os.getenv(env_name)
    if not v:
        raise ValueError(f"Missing required environment variable: {env_name}")
    return v


@dataclass
class AzureConfig:
    endpoint: str
    api_key: str
    api_version: str
    chat_deployment: str
    embedding_deployment: str
    embedding_batch_size: int = 256  # can be overridden by env

    @classmethod
    def from_env(cls, *, strict: bool = True) -> "AzureConfig":
        """
        strict=True -> require deployments and credentials in env
        """
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
        chat_dep = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
        embed_dep = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "")
        batch = int(os.getenv("AZURE_EMBED_BATCH", "256"))

        if strict:
            if not endpoint: raise ValueError("AZURE_OPENAI_ENDPOINT is required")
            if not api_key:  raise ValueError("AZURE_OPENAI_API_KEY is required")
            if not chat_dep: raise ValueError("AZURE_OPENAI_CHAT_DEPLOYMENT is required")
            if not embed_dep:raise ValueError("AZURE_OPENAI_EMBED_DEPLOYMENT is required")

        return cls(
            endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            chat_deployment=chat_dep,
            embedding_deployment=embed_dep,
            embedding_batch_size=batch,
        )


@dataclass
class AWSConfig:
    region: str
    llm_model_id: str
    embedding_model_id: str
    embedding_dimensions: Optional[int] = None
    assume_role_arn: Optional[str] = None
    external_id: Optional[str] = None
    profile: Optional[str] = None

    @classmethod
    def from_env(cls, *, strict: bool = True) -> "AWSConfig":
        """
        strict=True -> require region and model IDs from env
        """
        region = os.getenv("AWS_REGION", "")
        llm_model_id = os.getenv("BEDROCK_LLM_MODEL_ID", "")
        embed_model_id = os.getenv("BEDROCK_EMBED_MODEL_ID", "")
        embed_dims = os.getenv("BEDROCK_EMBED_DIMENSIONS")
        assume_arn = os.getenv("ASSUME_ROLE_ARN")
        external_id = os.getenv("AWS_EXTERNAL_ID")
        profile = os.getenv("AWS_PROFILE")

        if strict:
            if not region:        raise ValueError("AWS_REGION is required")
            if not llm_model_id:  raise ValueError("BEDROCK_LLM_MODEL_ID is required")
            if not embed_model_id:raise ValueError("BEDROCK_EMBED_MODEL_ID is required")

        return cls(
            region=region,
            llm_model_id=llm_model_id,
            embedding_model_id=embed_model_id,
            embedding_dimensions=int(embed_dims) if embed_dims else None,
            assume_role_arn=assume_arn,
            external_id=external_id,
            profile=profile,
        )