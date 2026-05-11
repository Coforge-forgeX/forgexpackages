# doc_extract/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict

class ExtractResult(TypedDict, total=False):
    text: str
    pages: List[str]
    metadata: Dict[str, Any]

class DocumentExtractor(ABC):
    @abstractmethod
    async def extract(
        self,
        *,
        content_bytes: bytes,
        ext: str,
        locale: str = "en-US",
        filename: Optional[str] = None,
        **kwargs: Any
    ) -> ExtractResult:
        ...