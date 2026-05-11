# doc_extract/providers/aws_textract.py
from __future__ import annotations
import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from dotenv import load_dotenv

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..base import DocumentExtractor, ExtractResult
from ..parsing import parse_textract_blocks

load_dotenv(os.path.abspath(os.path.join(os.getcwd(),'.env')))

class AWSTextractExtractor(DocumentExtractor):
    NAME = "aws_textract"  # registry key

    def __init__(self, *, region: Optional[str] = None, mode: str = "auto", s3_bucket: Optional[str] = None) -> None:
        self._client = boto3.client(
            "textract", 
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
        self._s3 = boto3.client(
            "s3", 
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
        self._mode = mode
        self._bucket = s3_bucket or os.getenv("TEXTRACT_S3_BUCKET")

    async def extract(
        self,
        *,
        content_bytes: bytes,
        ext: str,
        locale: str = "en-US",
        filename: Optional[str] = None,
        **kwargs: Any
    ) -> ExtractResult:
        t0 = time.time()
        desired_mode = kwargs.get("mode") or self._mode
        if desired_mode == "sync" or (desired_mode == "auto" and len(content_bytes) < 4_000_000):
            full_text, pages = await self._detect_document_text_bytes(content_bytes)
        else:
            bucket = kwargs.get("s3_bucket") or self._bucket
            if not bucket:
                raise ValueError("Textract async requires an S3 bucket. Provide 's3_bucket' or set TEXTRACT_S3_BUCKET.")
            s3_key = kwargs.get("s3_key") or self._make_s3_key(filename)
            await self._put_s3_object(bucket, s3_key, content_bytes)
            full_text, pages = await self._start_and_poll_text_detection(bucket, s3_key)

        return {
            "text": full_text,
            "pages": pages,
            "metadata": {
                "provider": "aws",
                "engine": "textract",
                "mode": desired_mode,
                "filename": filename,
                "elapsed_sec": round(time.time() - t0, 3),
            },
        }

    async def _detect_document_text_bytes(self, content_bytes: bytes) -> Tuple[str, list[str]]:
        loop = asyncio.get_running_loop()
        def _call():
            return self._client.detect_document_text(Document={"Bytes": content_bytes})
        resp = await loop.run_in_executor(None, _call)
        full_text, pages = parse_textract_blocks(resp.get("Blocks", []))
        return full_text, pages

    async def _put_s3_object(self, bucket: str, key: str, content: bytes) -> None:
        loop = asyncio.get_running_loop()
        def _put():
            self._s3.put_object(Bucket=bucket, Key=key, Body=content)
        await loop.run_in_executor(None, _put)

    async def _start_and_poll_text_detection(self, bucket: str, key: str) -> Tuple[str, list[str]]:
        loop = asyncio.get_running_loop()
        def _start():
            return self._client.start_document_text_detection(
                DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
            )
        start = await loop.run_in_executor(None, _start)
        job_id = start["JobId"]

        blocks = []
        next_token = None
        while True:
            await asyncio.sleep(1.5)
            def _get():
                return self._client.get_document_text_detection(JobId=job_id, NextToken=next_token) if next_token \
                    else self._client.get_document_text_detection(JobId=job_id)
            resp = await loop.run_in_executor(None, _get)
            status = resp.get("JobStatus")
            if status == "SUCCEEDED":
                blocks.extend(resp.get("Blocks", []))
                next_token = resp.get("NextToken")
                if not next_token:
                    break
            elif status in ("FAILED", "PARTIAL_SUCCESS"):
                raise RuntimeError(f"Textract job ended with status: {status}")
            else:
                continue

        full_text, pages = parse_textract_blocks(blocks)
        return full_text, pages

    def _make_s3_key(self, filename: Optional[str]) -> str:
        stem = Path(filename).name if filename else "document"
        return f"textract/{uuid.uuid4()}_{stem}"
