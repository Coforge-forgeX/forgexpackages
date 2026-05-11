
from __future__ import annotations
from typing import Optional, Dict, List
from abc import ABC, abstractmethod
from .types import EncryptionOptions

class StorageClient(ABC):
    """Provider-agnostic storage client interface (Strategy).

    All container/bucket names are passed via `container`.
    Object/blob names are passed via `key`.
    """

    # --- Write APIs ---
    @abstractmethod
    def upload_file(self, *, container: str, key: str, file_path: str, content_type: Optional[str] = None,
                    metadata: Optional[Dict[str, str]] = None, encryption: Optional[EncryptionOptions] = None,
                    overwrite: bool = True) -> None:
        """Upload from local path."""

    @abstractmethod
    def put_bytes(self, *, container: str, key: str, data: bytes, content_type: Optional[str] = None,
                  metadata: Optional[Dict[str, str]] = None, encryption: Optional[EncryptionOptions] = None,
                  overwrite: bool = True) -> None:
        """Upload raw bytes."""

    # --- Read APIs ---
    @abstractmethod
    def download_file(self, *, container: str, key: str, dest_path: str) -> None:
        """Download to local path."""

    @abstractmethod
    def get_bytes(self, *, container: str, key: str) -> bytes:
        """Read entire object to bytes."""

    # --- Object management ---
    @abstractmethod
    def delete_object(self, *, container: str, key: str) -> None:
        pass

    @abstractmethod
    def object_exists(self, *, container: str, key: str) -> bool:
        pass

    @abstractmethod
    def list_objects(self, *, container: str, prefix: str = "", recursive: bool = True,
                     max_results: Optional[int] = None) -> List[str]:
        pass

    @abstractmethod
    def copy_object(self, *, src_container: str, src_key: str, dest_container: str, dest_key: str,
                    if_source_etag: Optional[str] = None) -> None:
        pass

    # --- URLs ---
    @abstractmethod
    def generate_presigned_url(self, *, container: str, key: str, expires_in: int = 900,
                               method: str = "GET") -> str:
        pass

    # --- Metadata ---
    @abstractmethod
    def get_object_metadata(self, *, container: str, key: str) -> Dict[str, str]:
        pass
