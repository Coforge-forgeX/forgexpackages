
from __future__ import annotations
from typing import Optional, Dict, List
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

from .base import StorageClient
from .config import StorageSettings
from .types import EncryptionOptions
from .exceptions import StorageError, NotFoundError, ConflictError, AuthError

class AzureBlobClient(StorageClient):
    def _lazy_imports(self):
        try:
            from azure.storage import blob as az_blob
            from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
            from azure.core import exceptions as az_ex
        except ImportError as e:
            raise ImportError("azure-storage-blob is required for Azure provider. Install azure-storage-blob.") from e
        self._BlobServiceClient = BlobServiceClient
        self._ContentSettings = ContentSettings
        self._generate_blob_sas = generate_blob_sas
        self._BlobSasPermissions = BlobSasPermissions
        self._ResourceNotFoundError = getattr(az_ex, 'ResourceNotFoundError', Exception)
        self._ClientAuthenticationError = getattr(az_ex, 'ClientAuthenticationError', Exception)
        self._HttpResponseError = getattr(az_ex, 'HttpResponseError', Exception)

    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings
        self._lazy_imports()
        if settings.azure_connection_string:
            self._svc = self._BlobServiceClient.from_connection_string(settings.azure_connection_string)
        elif settings.azure_account_url and (settings.azure_sas_token or settings.azure_account_key):
            cred = settings.azure_sas_token or settings.azure_account_key
            self._svc = self._BlobServiceClient(account_url=settings.azure_account_url, credential=cred)
        else:
            # Fall back to env var if available
            conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if not conn:
                raise ValueError("Azure configuration missing: provide connection string or account_url+credential")
            self._svc = self._BlobServiceClient.from_connection_string(conn)
    
    def _get_account_name(self) -> str:
        """Extract account name from service client."""
        return str(self._svc.account_name) if self._svc.account_name else ""
    
    def _get_account_key(self) -> Optional[str]:
        """Extract account key from service client credential."""
        try:
            if hasattr(self._svc, 'credential') and hasattr(self._svc.credential, 'account_key'):
                return self._svc.credential.account_key
        except:
            pass
        return self._settings.azure_account_key

    # --- Helpers ---
    def _content_settings(self, content_type: Optional[str]):
        return self._ContentSettings(content_type=content_type) if content_type else None

    def _translate_error(self, err: Exception):
        if isinstance(err, self._ResourceNotFoundError):
            return NotFoundError(str(err))
        if isinstance(err, self._ClientAuthenticationError):
            return AuthError(str(err))
        if isinstance(err, self._HttpResponseError) and getattr(err, 'status_code', None) == 412:
            return ConflictError(str(err))
        return StorageError(str(err))

    # --- Interface ---
    def upload_file(self, *, container: str, key: str, file_path: str, content_type: Optional[str] = None,
                    metadata: Optional[Dict[str, str]] = None, encryption: Optional[EncryptionOptions] = None,
                    overwrite: bool = True) -> None:
        try:
            bc = self._svc.get_blob_client(container=container, blob=key)
            with open(file_path, 'rb') as data:
                bc.upload_blob(
                    data,
                    overwrite=overwrite,
                    metadata=metadata,
                    content_settings=self._content_settings(content_type),
                    encryption_scope=encryption.encryption_scope if encryption else None,
                )
        except Exception as e:  # azure-core exceptions
            raise self._translate_error(e)

    def put_bytes(self, *, container: str, key: str, data: bytes, content_type: Optional[str] = None,
                  metadata: Optional[Dict[str, str]] = None, encryption: Optional[EncryptionOptions] = None,
                  overwrite: bool = True) -> None:
        try:
            bc = self._svc.get_blob_client(container=container, blob=key)
            bc.upload_blob(
                data,
                overwrite=overwrite,
                metadata=metadata,
                content_settings=self._content_settings(content_type),
                encryption_scope=encryption.encryption_scope if encryption else None,
            )
        except Exception as e:
            raise self._translate_error(e)

    def download_file(self, *, container: str, key: str, dest_path: str) -> None:
        try:
            bc = self._svc.get_blob_client(container=container, blob=key)
            stream = bc.download_blob()
            os.makedirs(os.path.dirname(dest_path) or '.', exist_ok=True)
            with open(dest_path, 'wb') as f:
                for chunk in stream.chunks():
                    f.write(chunk)
        except Exception as e:
            raise self._translate_error(e)

    def get_bytes(self, *, container: str, key: str) -> bytes:
        try:
            bc = self._svc.get_blob_client(container=container, blob=key)
            stream = bc.download_blob()
            return stream.readall()
        except Exception as e:
            raise self._translate_error(e)

    def delete_object(self, *, container: str, key: str) -> None:
        try:
            bc = self._svc.get_blob_client(container=container, blob=key)
            bc.delete_blob()
        except Exception as e:
            raise self._translate_error(e)

    def object_exists(self, *, container: str, key: str) -> bool:
        try:
            bc = self._svc.get_blob_client(container=container, blob=key)
            bc.get_blob_properties()
            return True
        except self._ResourceNotFoundError:
            return False
        except Exception as e:
            raise self._translate_error(e)

    def list_objects(self, *, container: str, prefix: str = "", recursive: bool = True,
                     max_results: Optional[int] = None) -> List[str]:
        try:
            cc = self._svc.get_container_client(container)
            results: List[str] = []
            for blob in cc.list_blobs(name_starts_with=prefix):
                results.append(blob.name)
                if max_results and len(results) >= max_results:
                    return results
            return results
        except Exception as e:
            raise self._translate_error(e)

    def copy_object(self, *, src_container: str, src_key: str, dest_container: str, dest_key: str,
                    if_source_etag: Optional[str] = None) -> None:
        try:
            source_blob = self._svc.get_blob_client(src_container, src_key)
            source_url = source_blob.url
            dest_blob = self._svc.get_blob_client(dest_container, dest_key)
            dest_blob.start_copy_from_url(source_url, requires_sync=True)
        except Exception as e:
            raise self._translate_error(e)

    def generate_presigned_url(self, *, container: str, key: str, expires_in: int = 900,
                               method: str = "GET") -> str:
        """Generate a presigned URL (SAS token).
        
        Args:
            container: Container/bucket name
            key: Object/blob name
            expires_in: Expiration time in seconds (default: 900)
            method: HTTP method - "GET" or "PUT"
            
        Returns:
            Full URL with SAS token
        """
        account_name = self._get_account_name()
        account_key = self._get_account_key()
        
        if not account_name:
            raise StorageError("Could not determine Azure Storage account name")
        if not account_key:
            raise StorageError("SAS generation requires account key. Ensure connection string includes AccountKey or provide azure_account_key in settings")
            
        if method.upper() not in {"GET", "PUT"}:
            raise ValueError("Only GET and PUT are supported for SAS URLs")
            
        permissions = self._BlobSasPermissions(read=True) if method.upper() == "GET" else self._BlobSasPermissions(write=True, create=True)
        
        sas = self._generate_blob_sas(
            account_name=account_name,
            container_name=container,
            blob_name=key,
            account_key=account_key,
            permission=permissions,
            expiry=datetime.utcnow() + timedelta(seconds=expires_in),
        )
        
        return f"https://{account_name}.blob.core.windows.net/{container}/{key}?{sas}"

    def get_object_metadata(self, *, container: str, key: str) -> Dict[str, str]:
        try:
            bc = self._svc.get_blob_client(container=container, blob=key)
            props = bc.get_blob_properties()
            md = {k: str(v) for k, v in (props.metadata or {}).items()}
            md.update({
                "ContentLength": str(props.size),
                "ContentType": props.content_settings.content_type or "",
                "ETag": props.etag or "",
            })
            return md
        except Exception as e:
            raise self._translate_error(e)
