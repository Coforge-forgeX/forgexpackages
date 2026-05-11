import os
import logging
from .unified import UnifiedAIAdapter, AzureConfig, AWSConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_adapter_singleton = None

def get_unified_adapter() -> UnifiedAIAdapter:
    global _adapter_singleton
    if _adapter_singleton is not None:
        logger.info(f"🔄 Returning existing adapter singleton (provider: {_adapter_singleton._provider_name})")
        return _adapter_singleton

    provider = os.getenv("AI_PROVIDER", "azure").strip().lower()
    logger.info("=" * 80)
    logger.info(f"🚀 INITIALIZING AI ADAPTER - Provider from AI_PROVIDER env var: '{provider}'")
    logger.info("=" * 80)

    if provider == "azure":
        logger.info("☁️ Configuring AZURE OpenAI provider...")
        cfg = AzureConfig.from_env(strict=True)
        logger.info(f"   └─ Endpoint: {cfg.endpoint}")
        logger.info(f"   └─ Chat Deployment: {cfg.chat_deployment}")
        logger.info(f"   └─ Embed Deployment: {cfg.embedding_deployment}")
        _adapter_singleton = UnifiedAIAdapter(provider="azure", azure=cfg)
        logger.info("✅ Azure OpenAI adapter initialized successfully")
    elif provider == "aws":
        logger.info("🔶 Configuring AWS Bedrock provider...")
        cfg = AWSConfig.from_env(strict=True)
        logger.info(f"   └─ Region: {cfg.region}")
        logger.info(f"   └─ LLM Model ID: {cfg.llm_model_id}")
        logger.info(f"   └─ Embed Model ID: {cfg.embedding_model_id}")
        logger.info(f"   └─ Assume Role ARN: {cfg.assume_role_arn or 'None (using default credentials)'}")
        _adapter_singleton = UnifiedAIAdapter(provider="aws", aws=cfg)
        logger.info("✅ AWS Bedrock adapter initialized successfully")
    else:
        error_msg = f"❌ AI_PROVIDER must be 'azure' or 'aws', got: '{provider}'"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info("=" * 80)
    return _adapter_singleton
