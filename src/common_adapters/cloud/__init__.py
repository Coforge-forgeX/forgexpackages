"""
Cloud Abstraction Layer

Cloud-agnostic abstractions for:
- Cloud provider enum (Azure, AWS, GCP, Local)
- Secret management (KeyVault, SecretsManager, GCP Secret Manager, Env)
- Object storage (Blob, S3, GCS)

Agents create services by passing explicit configuration.
"""

from .provider import CloudProvider
from .secrets import (
    SecretProvider,
    EnvSecretProvider,
    AzureKeyVaultSecretProvider,
    AwsSecretsManagerProvider,
    GcpSecretManagerProvider,
    extract_from_json,
)
from .object_storage import (
    ObjectStorageService,
    AzureBlobStorageService,
    S3StorageService,
    GcsStorageService,
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
    "GcpSecretManagerProvider",
    "extract_from_json",
    # Object Storage
    "ObjectStorageService",
    "AzureBlobStorageService",
    "S3StorageService",
    "GcsStorageService",
    "BlobItem",
    "BlobDownload",
]
