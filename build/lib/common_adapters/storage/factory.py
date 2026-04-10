
from __future__ import annotations
from .config import StorageSettings
from .base import StorageClient

class StorageFactory:
    @staticmethod
    def from_settings(settings: StorageSettings) -> StorageClient:
        if settings.provider == "aws":
            from .s3_client import S3Client
            return S3Client(settings)
        elif settings.provider == "azure":
            from .azure_blob_client import AzureBlobClient
            return AzureBlobClient(settings)
        else:
            raise ValueError(f"Unsupported provider: {settings.provider}")

