"""
Object Storage Abstraction

Cloud-agnostic object storage supporting:
- Azure Blob Storage
- AWS S3- Google Cloud Storage (GCS)
Agent creates the appropriate service by passing explicit configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(slots=True)
class BlobItem:
    """Represents a blob/object in storage."""
    name: str


class BlobDownload:
    """Wrapper for downloaded blob content."""
    
    def __init__(self, payload: bytes):
        self._payload = payload

    def readall(self) -> bytes:
        return self._payload


class BlobHandle(Protocol):
    """Protocol for blob/object handles."""
    
    def exists(self) -> bool:
        ...


class ContainerLike(Protocol):
    """Protocol for container/bucket operations."""
    
    def list_blobs(self, name_starts_with: str) -> Iterable[BlobItem]:
        ...

    def download_blob(self, blob_name: str) -> BlobDownload:
        ...

    def get_blob_client(self, blob_name: str) -> BlobHandle:
        ...

    def upload_blob(self, *, name: str, data: str, overwrite: bool, content_type: str) -> None:
        ...


class ObjectStorageService(Protocol):
    """Protocol for object storage services."""
    
    def ensure_container(self, container_name: str) -> None:
        ...

    def get_container_client(self, container_name: str) -> ContainerLike:
        ...


class AzureBlobStorageService:
    """Azure Blob Storage implementation."""
    
    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: Azure Storage connection string
        """
        from azure.storage.blob import BlobServiceClient

        self._client = BlobServiceClient.from_connection_string(connection_string)

    def ensure_container(self, container_name: str) -> None:
        from azure.core.exceptions import ResourceExistsError

        try:
            self._client.get_container_client(container_name).create_container()
        except ResourceExistsError:
            pass

    def get_container_client(self, container_name: str):
        return self._client.get_container_client(container_name)


class S3BlobHandle:
    """S3 object handle for existence checks."""
    
    def __init__(self, s3_client, bucket: str, key: str):
        self._s3 = s3_client
        self._bucket = bucket
        self._key = key

    def exists(self) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=self._key)
            return True
        except Exception:
            return False


class S3ContainerClient:
    """S3 bucket operations wrapper."""
    
    def __init__(self, s3_client, bucket: str):
        self._s3 = s3_client
        self._bucket = bucket

    def list_blobs(self, name_starts_with: str):
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=name_starts_with):
            for item in page.get("Contents", []) or []:
                yield BlobItem(name=item["Key"])

    def download_blob(self, blob_name: str) -> BlobDownload:
        resp = self._s3.get_object(Bucket=self._bucket, Key=blob_name)
        return BlobDownload(resp["Body"].read())

    def get_blob_client(self, blob_name: str) -> S3BlobHandle:
        return S3BlobHandle(self._s3, self._bucket, blob_name)

    def upload_blob(self, *, name: str, data: str, overwrite: bool, content_type: str) -> None:
        if not overwrite:
            blob_handle = self.get_blob_client(name)
            if blob_handle.exists():
                return
        self._s3.put_object(
            Bucket=self._bucket,
            Key=name,
            Body=data.encode("utf-8"),
            ContentType=content_type,
        )


class S3StorageService:
    """AWS S3 storage implementation."""
    
    def __init__(self, region_name: str | None = None):
        """
        Args:
            region_name: AWS region (e.g., us-east-1)
        """
        import boto3

        self._s3 = boto3.client("s3", region_name=region_name)
        self._region = region_name

    def ensure_container(self, container_name: str) -> None:
        try:
            self._s3.head_bucket(Bucket=container_name)
        except Exception:
            kwargs = {"Bucket": container_name}
            if self._region and self._region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self._region}
            self._s3.create_bucket(**kwargs)

    def get_container_client(self, container_name: str) -> S3ContainerClient:
        return S3ContainerClient(self._s3, container_name)


# =============================================================================
# Google Cloud Storage (GCS)
# =============================================================================


class GcsBlobHandle:
    """GCS blob handle for existence checks."""
    
    def __init__(self, blob):
        self._blob = blob

    def exists(self) -> bool:
        return self._blob.exists()


class GcsContainerClient:
    """GCS bucket operations wrapper."""
    
    def __init__(self, bucket):
        self._bucket = bucket

    def list_blobs(self, name_starts_with: str):
        for blob in self._bucket.list_blobs(prefix=name_starts_with):
            yield BlobItem(name=blob.name)

    def download_blob(self, blob_name: str) -> BlobDownload:
        blob = self._bucket.blob(blob_name)
        return BlobDownload(blob.download_as_bytes())

    def get_blob_client(self, blob_name: str) -> GcsBlobHandle:
        return GcsBlobHandle(self._bucket.blob(blob_name))

    def upload_blob(self, *, name: str, data: str, overwrite: bool, content_type: str) -> None:
        blob = self._bucket.blob(name)
        if not overwrite and blob.exists():
            return
        blob.upload_from_string(data, content_type=content_type)


class GcsStorageService:
    """Google Cloud Storage implementation."""
    
    def __init__(self, project_id: str | None = None):
        """
        Args:
            project_id: GCP project ID. If None, uses default from environment.
        """
        from google.cloud import storage
        import os

        self._project_id = project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._client = storage.Client(project=self._project_id)

    def ensure_container(self, container_name: str) -> None:
        try:
            self._client.get_bucket(container_name)
        except Exception:
            self._client.create_bucket(container_name)

    def get_container_client(self, container_name: str) -> GcsContainerClient:
        bucket = self._client.bucket(container_name)
        return GcsContainerClient(bucket)
