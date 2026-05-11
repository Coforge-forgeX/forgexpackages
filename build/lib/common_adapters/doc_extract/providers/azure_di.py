# doc_extract/providers/azure_di.py
from __future__ import annotations
import asyncio, io
from typing import Any, Dict, Optional

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

from ..base import DocumentExtractor, ExtractResult

class AzureDIExtractor(DocumentExtractor):
    NAME = "azure_document_intelligence"  # registry key

    def __init__(self, *, endpoint: str, api_key: str, model: str = "prebuilt-read") -> None:
        self._client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(api_key))
        self._model = model

    async def extract(
        self,
        *,
        content_bytes: bytes,
        ext: str,
        locale: str = "en-US",
        filename: Optional[str] = None,
        **kwargs: Any
    ) -> ExtractResult:
        loop = asyncio.get_running_loop()

        def _run():
            # Wrap raw bytes in a file-like object to match IO[bytes]
            stream = io.BytesIO(content_bytes)
            poller = self._client.begin_analyze_document(
                model_id=self._model,
                body=stream,                                   # IO[bytes]
                content_type="application/octet-stream",       # recommended
                locale=locale,                                 # keyword-only
            )
            return poller.result()


        result = await loop.run_in_executor(None, _run)
        text = getattr(result, "content", "") or ""
        return {
            "text": text,
            "metadata": {
                "provider": "azure",
                "engine": "document_intelligence",
                "model": self._model,
                "filename": filename,
            },
        }