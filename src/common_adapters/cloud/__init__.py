"""
Cloud Abstraction Layer

Cloud-agnostic abstractions for:
- Cloud provider enum (Azure, AWS, Local)
- Secret management (KeyVault, SecretsManager, Env)
- Object storage (Blob, S3)

Agents create services by passing explicit configuration.
"""

from .provider import CloudProvider
from .secrets import (
    SecretProvider,
    EnvSecretProvider,
    AzureKeyVaultSecretProvider,
    AwsSecretsManagerProvider,
    extract_from_json,
)
from .object_storage import (
    ObjectStorageService,
    AzureBlobStorageService,
    S3StorageService,
    BlobItem,
    BlobDownload,
)

__all__ = [
    # Provider
    "CloudProvider",
    # Secrets
    "SecretProvider",
    "EnvSecretProvider",
    "AzureKeyVaultSecretProvider",
    "AwsSecretsManagerProvider",
    "extract_from_json",
    # Object Storage
    "ObjectStorageService",
    "AzureBlobStorageService",
    "S3StorageService",
    "BlobItem",
    "BlobDownload",
]
