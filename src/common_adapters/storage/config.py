
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal
import os

Provider = Literal["aws", "azure"]

@dataclass
class StorageSettings:
    """Settings for selecting and configuring the storage provider.

    Provide explicit fields or rely on provider SDK default resolution.
    """

    provider: Provider

    # --- AWS ---
    aws_region: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_endpoint_url: Optional[str] = None  # for custom endpoints/minio etc.

    # --- Azure ---
    azure_connection_string: Optional[str] = None
    azure_account_url: Optional[str] = None  # e.g., https://<account>.blob.core.windows.net
    azure_sas_token: Optional[str] = None    # starts with ?sv=...
    azure_account_key: Optional[str] = None  # for SAS generation if needed

    request_timeout_seconds: int = 60
    max_retries: int = 5

    @staticmethod
    def from_env() -> StorageSettings:
        """Create StorageSettings from environment variables.
        
        Environment Variables:
            STORAGE_PROVIDER: 'aws' or 'azure' (required)
            
            AWS:
                AWS_REGION: AWS region
                AWS_ACCESS_KEY_ID: AWS access key
                AWS_SECRET_ACCESS_KEY: AWS secret key
                AWS_SESSION_TOKEN: AWS session token (optional)
                AWS_ENDPOINT_URL: Custom S3 endpoint (optional)
            
            Azure:
                AZURE_STORAGE_CONNECTION_STRING: Azure connection string
                AZURE_STORAGE_ACCOUNT_URL: Azure account URL (optional)
                AZURE_STORAGE_SAS_TOKEN: Azure SAS token (optional)
                AZURE_STORAGE_ACCOUNT_KEY: Azure account key (optional)
            
            Common:
                STORAGE_TIMEOUT: Request timeout in seconds (default: 60)
                STORAGE_MAX_RETRIES: Maximum retry attempts (default: 5)
        """
        provider = os.getenv("STORAGE_PROVIDER", "").strip().lower()
        if provider not in {"aws", "azure"}:
            raise ValueError("STORAGE_PROVIDER must be 'aws' or 'azure'")
        
        return StorageSettings(
            provider=provider,
            # AWS settings
            aws_region=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            aws_endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),
            # Azure settings
            azure_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            azure_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
            azure_sas_token=os.getenv("AZURE_STORAGE_SAS_TOKEN"),
            azure_account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
            # Common settings
            request_timeout_seconds=int(os.getenv("STORAGE_TIMEOUT", "60")),
            max_retries=int(os.getenv("STORAGE_MAX_RETRIES", "5")),
        )
