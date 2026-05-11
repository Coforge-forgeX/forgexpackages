# doc_extract/reader.py
from __future__ import annotations
import os
from typing import Any, Dict, Optional, Type

from .base import DocumentExtractor, ExtractResult
from .providers.azure_di import AzureDIExtractor
from .providers.aws_textract import AWSTextractExtractor

class DocReader:
    """
    Provider-agnostic document reader.
    Usage: reader = DocReader(provider="aws_textract"); await reader.read(bytes, ext="pdf")
    """
    _REGISTRY: Dict[str, Type[DocumentExtractor]] = {}

    # --- static registration (built-ins) ---
    @classmethod
    def _register_builtins(cls) -> None:
        cls.register(AzureDIExtractor.NAME, AzureDIExtractor)
        cls.register(AWSTextractExtractor.NAME, AWSTextractExtractor)

    @classmethod
    def register(cls, name: str, extractor_cls: Type[DocumentExtractor]) -> None:
        cls._REGISTRY[name.lower()] = extractor_cls

    def __init__(self, *, provider: Optional[str] = None, **provider_cfg: Any) -> None:
        # Default from env if not supplied
        provider = (provider or os.getenv("DOC_READER_PROVIDER") or "azure_document_intelligence").lower()
        if not self._REGISTRY:
            self._register_builtins()
        if provider not in self._REGISTRY:
            supported = ", ".join(sorted(self._REGISTRY.keys()))
            raise ValueError(f"Unknown provider '{provider}'. Supported: {supported}")

        self._provider_name = provider
        self._provider_cfg = provider_cfg
        self._extractor = self._build_extractor(provider, provider_cfg)

    def _build_extractor(self, provider: str, cfg: Dict[str, Any]) -> DocumentExtractor:
        cls = self._REGISTRY[provider]
        # Supply sensible env-driven defaults so callers don't branch
        if provider == AzureDIExtractor.NAME:
            cfg = {
                "endpoint": cfg.get("endpoint") or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
                "api_key": cfg.get("api_key") or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY"),
                "model": cfg.get("model") or os.getenv("AZURE_DI_MODEL", "prebuilt-read"),
            }
            if not cfg["endpoint"] or not cfg["api_key"]:
                raise ValueError("Azure DI requires AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and KEY.")
        elif provider == AWSTextractExtractor.NAME:
            cfg = {
                "region": cfg.get("region") or os.getenv("AWS_REGION"),
                "mode": cfg.get("mode") or os.getenv("TEXTRACT_MODE", "auto"),
                "s3_bucket": cfg.get("s3_bucket") or os.getenv("TEXTRACT_S3_BUCKET"),
            }
        return cls(**cfg)  # type: ignore[arg-type]

    async def read(
        self,
        *,
        bytes: bytes,
        ext: str,
        locale: str = "en-US",
        filename: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Returns plain text. Use `.read_full(...)` if you need pages/metadata.
        """
        result = await self.read_full(bytes=bytes, ext=ext, locale=locale, filename=filename, **kwargs)
        return result.get("text", "")

    async def read_full(
        self,
        *,
        bytes: bytes,
        ext: str,
        locale: str = "en-US",
        filename: Optional[str] = None,
        **kwargs: Any
    ) -> ExtractResult:
        return await self._extractor.extract(
            content_bytes=bytes, ext=ext, locale=locale, filename=filename, **kwargs
        )

    @property
    def provider(self) -> str:
        return self._provider_name