
from __future__ import annotations
from typing import Optional, Dict, List
import os

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from .base import StorageClient
from .config import StorageSettings
from .types import EncryptionOptions
from .exceptions import StorageError, NotFoundError, ConflictError, AuthError

class S3Client(StorageClient):
    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings
        boto_config = BotoConfig(
            region_name=settings.aws_region,
            retries={"max_attempts": settings.max_retries, "mode": "standard"},
            read_timeout=settings.request_timeout_seconds,
            connect_timeout=min(10, settings.request_timeout_seconds),
        )
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token,
            region_name=settings.aws_region,
        )
        self._s3 = session.client("s3", endpoint_url=settings.aws_endpoint_url, config=boto_config)

    # --- Helpers ---
    def _translate_error(self, err: ClientError) -> StorageError:
        code = err.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return NotFoundError(str(err))
        if code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
            return AuthError(str(err))
        if code in {"PreconditionFailed"}:
            return ConflictError(str(err))
        return StorageError(str(err))

    def _put_extra_args(self, content_type: Optional[str], metadata: Optional[Dict[str, str]],
                        encryption: Optional[EncryptionOptions]) -> Dict[str, str]:
        extra: Dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        if metadata:
            extra["Metadata"] = metadata
        if encryption:
            if encryption.sse:
                extra["ServerSideEncryption"] = encryption.sse
            if encryption.kms_key_id:
                extra["SSEKMSKeyId"] = encryption.kms_key_id
        return extra

    # --- Interface ---
    def upload_file(self, *, container: str, key: str, file_path: str, content_type: Optional[str] = None,
                    metadata: Optional[Dict[str, str]] = None, encryption: Optional[EncryptionOptions] = None,
                    overwrite: bool = True) -> None:
        try:
            extra = self._put_extra_args(content_type, metadata, encryption)
            if not overwrite:
                # PutObject does not support If-None-Match directly in boto3
                # Perform a HEAD first to detect existence when overwrite=False
                try:
                    self._s3.head_object(Bucket=container, Key=key)
                    raise ConflictError(f"Object {container}/{key} already exists and overwrite=False")
                except ClientError as ce:
                    code = ce.response.get("Error", {}).get("Code")
                    if code not in {"404", "NoSuchKey", "NotFound"}:
                        raise self._translate_error(ce)
            with open(file_path, 'rb') as f:
                self._s3.put_object(Bucket=container, Key=key, Body=f, **extra)
        except ClientError as e:
            raise self._translate_error(e)

    def put_bytes(self, *, container: str, key: str, data: bytes, content_type: Optional[str] = None,
                  metadata: Optional[Dict[str, str]] = None, encryption: Optional[EncryptionOptions] = None,
                  overwrite: bool = True) -> None:
        try:
            extra = self._put_extra_args(content_type, metadata, encryption)
            if not overwrite:
                try:
                    self._s3.head_object(Bucket=container, Key=key)
                    raise ConflictError(f"Object {container}/{key} already exists and overwrite=False")
                except ClientError as ce:
                    code = ce.response.get("Error", {}).get("Code")
                    if code not in {"404", "NoSuchKey", "NotFound"}:
                        raise self._translate_error(ce)
            self._s3.put_object(Bucket=container, Key=key, Body=data, **extra)
        except ClientError as e:
            raise self._translate_error(e)

    def download_file(self, *, container: str, key: str, dest_path: str) -> None:
        try:
            resp = self._s3.get_object(Bucket=container, Key=key)
            body = resp['Body']
            os.makedirs(os.path.dirname(dest_path) or '.', exist_ok=True)
            with open(dest_path, 'wb') as f:
                # Use iter_chunks if available; fallback to manual reads for compatibility
                if hasattr(body, 'iter_chunks'):
                    for chunk in body.iter_chunks(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                else:
                    while True:
                        chunk = body.read(1024*1024)
                        if not chunk:
                            break
                        f.write(chunk)
        except ClientError as e:
            raise self._translate_error(e)

    def get_bytes(self, *, container: str, key: str) -> bytes:
        try:
            resp = self._s3.get_object(Bucket=container, Key=key)
            return resp['Body'].read()
        except ClientError as e:
            raise self._translate_error(e)

    def delete_object(self, *, container: str, key: str) -> None:
        try:
            self._s3.delete_object(Bucket=container, Key=key)
        except ClientError as e:
            raise self._translate_error(e)

    def object_exists(self, *, container: str, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=container, Key=key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise self._translate_error(e)

    def list_objects(self, *, container: str, prefix: str = "", recursive: bool = True,
                     max_results: Optional[int] = None) -> List[str]:
        try:
            paginator = self._s3.get_paginator('list_objects_v2')
            kwargs = {"Bucket": container, "Prefix": prefix}
            if not recursive:
                kwargs['Delimiter'] = '/'
            results: List[str] = []
            for page in paginator.paginate(**kwargs):
                for obj in page.get('Contents', []):
                    results.append(obj['Key'])
                    if max_results and len(results) >= max_results:
                        return results
            return results
        except ClientError as e:
            raise self._translate_error(e)

    def copy_object(self, *, src_container: str, src_key: str, dest_container: str, dest_key: str,
                    if_source_etag: Optional[str] = None) -> None:
        try:
            copy_source = {"Bucket": src_container, "Key": src_key}
            extra = {}
            if if_source_etag:
                extra["CopySourceIfMatch"] = if_source_etag
            self._s3.copy_object(Bucket=dest_container, Key=dest_key, CopySource=copy_source, **extra)
        except ClientError as e:
            raise self._translate_error(e)

    def generate_presigned_url(self, *, container: str, key: str, expires_in: int = 900,
                               method: str = "GET") -> str:
        try:
            method_map = {"GET": "get_object", "PUT": "put_object"}
            op = method_map.get(method.upper())
            if not op:
                raise ValueError("Only GET and PUT are supported for presigned URLs")
            return self._s3.generate_presigned_url(
                ClientMethod=op,
                Params={"Bucket": container, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise self._translate_error(e)

    def get_object_metadata(self, *, container: str, key: str) -> Dict[str, str]:
        try:
            resp = self._s3.head_object(Bucket=container, Key=key)
            md = {k: str(v) for k, v in resp.get('Metadata', {}).items()}
            md.update({
                "ContentLength": str(resp.get('ContentLength', '')),
                "ContentType": resp.get('ContentType', ''),
                "ETag": resp.get('ETag', ''),
            })
            return md
        except ClientError as e:
            raise self._translate_error(e)
