from __future__ import annotations
import os
import logging
from typing import List, Sequence, Dict, Optional
from openai import AsyncAzureOpenAI
from ..config import AzureConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AzureProvider:
    """Azure OpenAI: chat + embeddings via deployment names from environment variables."""

    def __init__(self, cfg: AzureConfig) -> None:
        self.cfg = cfg
        
        logger.info("=" * 80)
        logger.info("☁️ AZURE OPENAI PROVIDER INITIALIZATION")
        logger.info("=" * 80)
        logger.info(f"   Endpoint: {cfg.endpoint}")
        logger.info(f"   API Version: {cfg.api_version}")
        logger.info(f"   Chat Deployment: {cfg.chat_deployment}")
        logger.info(f"   Embedding Deployment: {cfg.embedding_deployment}")
        logger.info(f"   Embedding Batch Size: {cfg.embedding_batch_size}")
        
        self.client = AsyncAzureOpenAI(
            api_key=cfg.api_key,
            api_version=cfg.api_version,
            azure_endpoint=cfg.endpoint
        )
        
        logger.info("✅ Azure OpenAI Provider initialized successfully")
        logger.info("=" * 80)

    async def acomplete(
        self,
        *,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        logger.info("=" * 80)
        logger.info("☁️ AZURE OPENAI LLM CALL")
        logger.info("=" * 80)
        
        # Resolve defaults from environment if not provided
        if temperature is None:
            temperature = float(os.getenv("AZURE_CHAT_TEMPERATURE", "0.2"))
        if max_tokens is None and os.getenv("AZURE_CHAT_MAX_TOKENS"):
            max_tokens = int(os.getenv("AZURE_CHAT_MAX_TOKENS", "0"))

        if not messages and prompt:
            messages = [{"role": "user", "content": prompt}]
        if not messages:
            logger.error("❌ No messages or prompt provided")
            raise ValueError("Provide either prompt or messages")

        logger.info(f"   └─ Deployment: {self.cfg.chat_deployment}")
        logger.info(f"   └─ Temperature: {temperature}")
        logger.info(f"   └─ Max Tokens: {max_tokens}")
        logger.info(f"   └─ Messages count: {len(messages)}")

        try:
            logger.info(f"   └─ Calling Azure OpenAI API...")
            resp = await self.client.chat.completions.create(
                model=self.cfg.chat_deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            logger.info(f"   ✅ Azure response received")
            logger.info(f"   └─ Response length: {len(content)} chars")
            logger.info("=" * 80)
            return content
        except Exception as e:
            logger.error(f"❌ Error calling Azure OpenAI: {str(e)}")
            logger.info("=" * 80)
            return "Error while calling acomplete... please try later"

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        logger.info(f"🔍 Azure embeddings requested for {len(texts)} texts")
        try:
            vectors: List[List[float]] = []
            n = len(texts)
            bs = max(1, self.cfg.embedding_batch_size)
            logger.info(f"   └─ Processing in batches of {bs}")
            
            for i in range(0, n, bs):
                batch = list(texts[i:i+bs])
                resp = await self.client.embeddings.create(
                    model=self.cfg.embedding_deployment,
                    input=batch
                )
                vectors.extend([d.embedding for d in resp.data])
            
            logger.info(f"   ✅ Generated {len(vectors)} embeddings")
            return vectors
        except Exception as e:
            logger.error(f"❌ Error calling Azure embeddings: {str(e)}")
            raise