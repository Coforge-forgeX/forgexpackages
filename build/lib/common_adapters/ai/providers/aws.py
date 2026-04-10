from __future__ import annotations
import os
import json
import time
import uuid
import asyncio
import logging
from typing import List, Sequence, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..config import AWSConfig

import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AWSProvider:
    """
    AWS Bedrock runtime wrapper:
      - LLM -> Anthropic Claude (invoke_model)
      - Embeddings -> Titan v2 (optionally dimensions) or v1
    Reads all model IDs, region, and STS details from environment via AWSConfig.
    """

    def __init__(self, cfg: AWSConfig) -> None:
        self.cfg = cfg
        
        logger.info("=" * 80)
        logger.info("🔶 AWS BEDROCK PROVIDER INITIALIZATION")
        logger.info("=" * 80)
        logger.info(f"   Region: {cfg.region}")
        logger.info(f"   LLM Model ID: {cfg.llm_model_id}")
        logger.info(f"   Embed Model ID: {cfg.embedding_model_id}")
        logger.info(f"   Profile: {cfg.profile or 'Default'}")
        logger.info(f"   Assume Role ARN: {cfg.assume_role_arn or 'None'}")
        logger.info(f"   External ID: {'***' if cfg.external_id else 'None'}")

        # Base session (optional profile)
        if cfg.profile:
            logger.info(f"   └─ Creating session with profile: {cfg.profile}")
            self._base_session = boto3.Session(profile_name=cfg.profile, region_name=cfg.region)
        else:
            logger.info(f"   └─ Creating session with default credentials")
            self._base_session = boto3.Session(region_name=cfg.region)

        self._region = cfg.region
        logger.info(f"   └─ Initializing STS client for region: {self._region}")
        self._sts = self._base_session.client("sts", region_name=self._region)

        self._assumed_session: Optional[boto3.Session] = None
        self._role_expiry_epoch: int = 0

        logger.info("   └─ Creating initial assumed session...")
        self._refresh_assumed_session()  # create initial session
        logger.info("✅ AWS Bedrock Provider initialized successfully")
        logger.info("=" * 80)

    def _refresh_assumed_session(self) -> None:
        now = int(time.time())
        if self._assumed_session and now < (self._role_expiry_epoch - 60):
            logger.debug(f"Assumed session still valid (expires in {self._role_expiry_epoch - now}s)")
            return

        if not self.cfg.assume_role_arn:
            logger.info("No assume_role_arn provided, using base session credentials")
            self._assumed_session = self._base_session
            # Long window to skip frequent checks when not assuming a role
            self._role_expiry_epoch = now + 6 * 3600
            return

        kwargs = {
            "RoleArn": self.cfg.assume_role_arn,
            "RoleSessionName": f"ai-unified-{uuid.uuid4().hex[:8]}",
        }
        if self.cfg.external_id:
            kwargs["ExternalId"] = self.cfg.external_id

        logger.info(f"🔐 Assuming IAM role: {self.cfg.assume_role_arn}")
        try:
            resp = self._sts.assume_role(**kwargs)
        except (ClientError, BotoCoreError) as e:
            logger.error(f"❌ STS AssumeRole failed: {e}")
            raise RuntimeError(f"STS AssumeRole failed: {e}") from e

        creds = resp["Credentials"]
        logger.info(f"✅ Received temporary credentials, expires at: {creds['Expiration']}")
        self._role_expiry_epoch = int(creds["Expiration"].timestamp())

        self._assumed_session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=self._region,
        )
        logger.info("✅ Assumed session created successfully")

    async def acomplete(
        self,
        *,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        logger.info("=" * 80)
        logger.info("🔶 AWS BEDROCK LLM CALL")
        logger.info("=" * 80)
        
        self._refresh_assumed_session()
        logger.info(f"   └─ Creating bedrock-runtime client (region: {self._region})")
        client = self._assumed_session.client("bedrock-runtime", region_name=self._region)

        # Resolve defaults from environment if not provided
        if temperature is None:
            temperature = float(os.getenv("BEDROCK_LLM_TEMPERATURE", "0.2"))
        if max_tokens is None and os.getenv("BEDROCK_LLM_MAX_TOKENS"):
            max_tokens = int(os.getenv("BEDROCK_LLM_MAX_TOKENS", "0"))

        logger.info(f"   └─ Model ID: {self.cfg.llm_model_id}")
        logger.info(f"   └─ Temperature: {temperature}")
        logger.info(f"   └─ Max Tokens: {max_tokens or 4096}")

        user_text = prompt or ""
        if messages:
            # Compact user messages -> single user text for Claude
            user_texts = [m["content"] for m in messages if m.get("role") == "user"]
            if user_texts:
                user_text = "\n\n".join(user_texts)
            logger.info(f"   └─ Messages count: {len(messages)}")

        if not user_text:
            logger.error("❌ No user input provided to acomplete")
            raise ValueError("Provide either prompt or messages with at least one user input")

        logger.info(f"   └─ Input length: {len(user_text)} chars")

        loop = asyncio.get_running_loop()

        def _invoke() -> str:
            # For Bedrock Claude:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens or 4096,
                "temperature": temperature,
                "messages": [{"role": "user", "content": [{"type": "text", "text": user_text}]}],
            }
            logger.info(f"   └─ Invoking Bedrock model: {self.cfg.llm_model_id}")
            try:
                resp = client.invoke_model(modelId=self.cfg.llm_model_id, body=json.dumps(body))
                data = json.loads(resp["body"].read())
                logger.info(f"   ✅ Bedrock response received")
                logger.debug(f"      Response data: {data}")
                
                for choice in data.get("choices", []):
                    if choice.get("message"):
                        message = choice.get("message")
                        content = message.get("content", "")
                        logger.info(f"   └─ Response length: {len(content)} chars")
                        logger.info("=" * 80)
                        return content
                return ""
            except (ClientError, BotoCoreError) as e:
                logger.error(f"❌ Bedrock invoke_model failed: {e}")
                logger.info("=" * 80)
                raise RuntimeError(f"Bedrock invoke_model (LLM) failed: {e}") from e

        return await loop.run_in_executor(None, _invoke)

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        self._refresh_assumed_session()
        print("[DEBUG] Creating bedrock-runtime client for embeddings.")
        client = self._assumed_session.client("bedrock-runtime", region_name=self._region)

        loop = asyncio.get_running_loop()
        vectors: List[List[float]] = []

        async def _one(txt: str) -> List[float]:
            payload = {"inputText": txt}
            # For Titan v2, you can set dimensions via env / config
            if self.cfg.embedding_dimensions is not None and (
                ":v2" in self.cfg.embedding_model_id or self.cfg.embedding_model_id.endswith("-v2:0")
            ):
                payload["dimensions"] = self.cfg.embedding_dimensions

            def _invoke() -> List[float]:
                print(f"[DEBUG] Invoking embedding model {self.cfg.embedding_model_id}")
                try:
                    print(f"[DEBUG] EMBED PAYLOAD{payload}")
                    resp = client.invoke_model(
                        modelId=self.cfg.embedding_model_id,
                        body=json.dumps(payload),
                        contentType="application/json",
                        accept="application/json",
                        trace='ENABLED_FULL'
                    )
                    print(f"[DEBUG] Invoking embedding model {resp}")
                    body = json.loads(resp["body"].read())
                    return body["embedding"]
                except (ClientError, BotoCoreError) as e:
                    print(f"[ERROR] Bedrock invoke_model (Embeddings) failed: {e}")
                    raise RuntimeError(f"Bedrock invoke_model (Embeddings) failed: {e}") from e

            return await loop.run_in_executor(None, _invoke)

        for t in texts:
            print(f"[DEBUG] Embedding text: {t}")
            vec = await _one(t)
            vectors.append(vec)

        return np.array(vectors)