"""
TrustAI API Endpoints Configuration

Centralized endpoint definitions for TrustAI API.
Update BASE_URL environment variable to change the TrustAI API endpoint.
"""

import os

class TrustAIEndpoints:
    """TrustAI API endpoint definitions."""

    # Base URL - can be overridden with environment variable
    BASE_URL = os.getenv(
        "TRUSTAI_BASE_URL",
        "https://forgex-dev-trustai-qag.azurewebsites.net"
    )

    # Admin endpoints (require master API key)
    REGISTER_APP = f"{BASE_URL}/trustai-api/admin/apps"

    # API Key management endpoints
    GENERATE_API_KEY = f"{BASE_URL}/api/v1/api-keys/"
    LIST_API_KEYS = f"{BASE_URL}/api/v1/api-keys/"  # GET with ?user_id=<app_id>

    # Guardrails configuration endpoints
    GET_GUARDRAILS_CONFIG = f"{BASE_URL}/trustai-api/guardrails/configuration"
    UPDATE_GUARDRAILS_CONFIG = f"{BASE_URL}/trustai-api/guardrails/configuration/batch"
    GET_DEFAULT_CONFIG = f"{BASE_URL}/trustai-api/guardrails/default-config"

    # LLM call endpoint
    CHAT_COMPLETIONS = f"{BASE_URL}/trustai-api/ai-gateway/chat/completions"

    @classmethod
    def get_base_url(cls) -> str:
        """Get the configured base URL."""
        return cls.BASE_URL

    @classmethod
    def set_base_url(cls, url: str):
        """Set a custom base URL (useful for testing or different environments)."""
        cls.BASE_URL = url
        cls._update_endpoints()

    @classmethod
    def _update_endpoints(cls):
        """Update all endpoint URLs when base URL changes."""
        cls.REGISTER_APP = f"{cls.BASE_URL}/trustai-api/admin/apps"
        cls.GENERATE_API_KEY = f"{cls.BASE_URL}/api/v1/api-keys/"
        cls.LIST_API_KEYS = f"{cls.BASE_URL}/api/v1/api-keys/"
        cls.GET_GUARDRAILS_CONFIG = f"{cls.BASE_URL}/trustai-api/guardrails/configuration"
        cls.UPDATE_GUARDRAILS_CONFIG = f"{cls.BASE_URL}/trustai-api/guardrails/configuration/batch"
        cls.GET_DEFAULT_CONFIG = f"{cls.BASE_URL}/trustai-api/guardrails/default-config"
        cls.CHAT_COMPLETIONS = f"{cls.BASE_URL}/trustai-api/ai-gateway/chat/completions"


# Environment variable keys
class TrustAIEnvVars:
    """Environment variable names for TrustAI configuration."""

    MASTER_API_KEY = "TRUSTAI_MASTER_API_KEY"
    BASE_URL = "TRUSTAI_BASE_URL"
    API_KEY_LIFETIME_DAYS = "TRUSTAI_API_KEY_LIFETIME_DAYS"
    DEFAULT_LIFETIME_DAYS = 365

    @classmethod
    def get_master_api_key(cls) -> str:
        """Get the master API key from environment."""
        key = os.getenv(cls.MASTER_API_KEY)
        if not key:
            raise ValueError(
                f"Environment variable {cls.MASTER_API_KEY} is not set. "
                "This key is required for workspace registration and API key generation."
            )
        return key

    @classmethod
    def get_api_key_lifetime(cls) -> int:
        """Get the API key lifetime in days from environment."""
        lifetime = os.getenv(cls.API_KEY_LIFETIME_DAYS)
        if lifetime:
            try:
                return int(lifetime)
            except ValueError:
                pass
        return cls.DEFAULT_LIFETIME_DAYS
