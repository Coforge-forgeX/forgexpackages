# Environment variable keys
import os

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