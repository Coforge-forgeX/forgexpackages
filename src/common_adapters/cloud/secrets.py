"""
Secret Management

Cloud-agnostic secret retrieval supporting:
- Environment variables
- Azure Key Vault
- AWS Secrets Manager

Agent decides which provider to use and passes explicit configuration.
"""

from __future__ import annotations

import json
from typing import Protocol


class SecretProvider(Protocol):
    """Protocol for secret providers."""
    
    def get_secret(self, secret_name: str, default_value: str = "") -> str:
        """Retrieve a secret by name."""
        ...


class EnvSecretProvider:
    """Retrieve secrets from environment variables."""
    
    def __init__(self, env_getter=None):
        """
        Args:
            env_getter: Optional callable to get env vars. Defaults to os.getenv.
        """
        import os
        self._get_env = env_getter or os.getenv
    
    def get_secret(self, secret_name: str, default_value: str = "") -> str:
        return self._get_env(secret_name, default_value)


class AzureKeyVaultSecretProvider:
    """Retrieve secrets from Azure Key Vault."""
    
    def __init__(self, keyvault_url: str):
        """
        Args:
            keyvault_url: Full URL to the Key Vault (e.g., https://myvault.vault.azure.net)
        """
        self._client = None
        if not keyvault_url:
            return
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            self._client = SecretClient(
                vault_url=keyvault_url,
                credential=DefaultAzureCredential(),
            )
        except Exception:
            self._client = None

    def get_secret(self, secret_name: str, default_value: str = "") -> str:
        if not self._client:
            return default_value
        try:
            return self._client.get_secret(secret_name).value
        except Exception:
            return default_value


class AwsSecretsManagerProvider:
    """Retrieve secrets from AWS Secrets Manager."""
    
    def __init__(self, region_name: str | None = None):
        """
        Args:
            region_name: AWS region (e.g., us-east-1)
        """
        self._client = None
        try:
            import boto3

            self._client = boto3.client("secretsmanager", region_name=region_name)
        except Exception:
            self._client = None

    def get_secret(self, secret_name: str, default_value: str = "") -> str:
        if not self._client:
            return default_value
        try:
            response = self._client.get_secret_value(SecretId=secret_name)
            if "SecretString" in response:
                return response["SecretString"]
            if "SecretBinary" in response:
                return response["SecretBinary"].decode("utf-8")
            return default_value
        except Exception:
            return default_value


def extract_from_json(secret_payload: str, key: str, fallback: str = "") -> str:
    """
    Extract a field from a JSON secret payload.
    
    Args:
        secret_payload: JSON string containing the secret
        key: Key to extract from the JSON object
        fallback: Value to return if extraction fails
        
    Returns:
        Extracted value or fallback
    """
    try:
        data = json.loads(secret_payload)
        if isinstance(data, dict):
            return str(data.get(key, fallback))
    except Exception:
        pass
    return fallback
