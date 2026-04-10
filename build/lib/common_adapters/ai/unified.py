from __future__ import annotations
from typing import List, Dict, Optional, Sequence
import logging
from .config import AzureConfig, AWSConfig
from .providers.azure import AzureProvider
from .providers.aws import AWSProvider
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UnifiedAIAdapter:
    """
    Single entry point for both LLM and Embeddings across Azure and AWS.

    If a provider config is not passed, the adapter will load from environment
    variables using AzureConfig.from_env(strict=True) or AWSConfig.from_env(strict=True).
    """

    def __init__(
        self,
        *,
        provider: str,             # "azure" | "aws"
        azure: Optional[AzureConfig] = None,
        aws: Optional[AWSConfig] = None,
    ) -> None:
        p = provider.lower().strip()
        if p not in ("azure", "aws"):
            raise ValueError("provider must be 'azure' or 'aws'")
        self._provider_name = p

        logger.info(f"🔧 Initializing UnifiedAIAdapter with provider: {p.upper()}")
        
        if p == "azure":
            logger.info("   └─ Creating AzureProvider instance...")
            self._provider = AzureProvider(azure or AzureConfig.from_env(strict=True))
            logger.info("   ✅ AzureProvider ready")
        else:
            logger.info("   └─ Creating AWSProvider instance...")
            self._provider = AWSProvider(aws or AWSConfig.from_env(strict=True))
            logger.info("   ✅ AWSProvider ready")

    # ---------------- LLM ----------------

    async def acomplete(
        self,
        *,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        logger.info(f"🔄 UnifiedAIAdapter.acomplete() called (provider: {self._provider_name.upper()})")
        return await self._provider.acomplete(
            prompt=prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ------------- Embeddings -------------

    async def embed(self, texts: Sequence[str]) -> np.ndarray:
        vectors = await self._provider.embed(texts)

        # ✅ Normalize for LightRAG
        if isinstance(vectors, np.ndarray):
            return vectors

        return np.array(vectors, dtype="float32")


    async def embed_one(self, text: str) -> List[float]:
        return (await self.embed([text]))[0]