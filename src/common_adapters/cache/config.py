import os
from dotenv import load_dotenv
from typing import Dict, Any


class CacheConfig:
    """
    Configuration class for managing cache-related environment variables.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern to ensure only one instance of CacheConfig exists."""
        if cls._instance is None:
            cls._instance = super(CacheConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize configuration from environment variables."""
        if not CacheConfig._initialized:
            self._load_env()
            CacheConfig._initialized = True

    def _load_env(self):
        """Load environment variables."""
        load_dotenv()

        # Redis Provider Configuration
        self.redis_provider = os.getenv("REDIS_PROVIDER", "azure").lower()

        # Azure Redis Configuration
        self.azure_redis_host = os.getenv("AZURE_REDIS_HOST", "")
        self.azure_redis_port = int(os.getenv("AZURE_REDIS_PORT", "6380"))
        self.azure_redis_password = os.getenv("AZURE_REDIS_PASSWORD", "")
        self.azure_redis_ssl = os.getenv("AZURE_REDIS_SSL", "true").lower() == "true"

        # AWS Redis Configuration (ElastiCache)
        self.aws_redis_host = os.getenv("AWS_REDIS_HOST", "")
        self.aws_redis_port = int(os.getenv("AWS_REDIS_PORT", "6379"))
        self.aws_redis_password = os.getenv("AWS_REDIS_PASSWORD", "")
        self.aws_redis_ssl = os.getenv("AWS_REDIS_SSL", "false").lower() == "true"

        # Generic Redis Configuration (fallback for backward compatibility)
        self.redis_host = os.getenv("REDIS_HOST", "")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", "")

        # Common Configuration
        self.redis_expiry_seconds = int(os.getenv("REDIS_EXPIRY_SECONDS", "900"))

    def get_azure_config(self) -> Dict[str, Any]:
        """
        Get Azure Redis configuration.

        Returns:
            Dict[str, Any]: Dictionary containing Azure Redis connection parameters.
        """
        return {
            "host": self.azure_redis_host,
            "port": self.azure_redis_port,
            "password": self.azure_redis_password,
            "ssl": self.azure_redis_ssl,
            "expiry_seconds": self.redis_expiry_seconds,
        }

    def get_aws_config(self) -> Dict[str, Any]:
        """
        Get AWS Redis (ElastiCache) configuration.

        Returns:
            Dict[str, Any]: Dictionary containing AWS Redis connection parameters.
        """
        return {
            "host": self.aws_redis_host,
            "port": self.aws_redis_port,
            "password": self.aws_redis_password,
            "ssl": self.aws_redis_ssl,
            "expiry_seconds": self.redis_expiry_seconds,
        }

    def get_generic_config(self) -> Dict[str, Any]:
        """
        Get generic Redis configuration (for backward compatibility).

        Returns:
            Dict[str, Any]: Dictionary containing generic Redis connection parameters.
        """
        return {
            "host": self.redis_host,
            "port": self.redis_port,
            "password": self.redis_password,
            "expiry_seconds": self.redis_expiry_seconds,
        }

    def get_provider(self) -> str:
        """
        Get the configured Redis provider.

        Returns:
            str: The Redis provider name (azure, aws, or generic).
        """
        return self.redis_provider

    def reload(self):
        """Reload configuration from environment variables."""
        self._load_env()


# Singleton instance for easy access
config = CacheConfig()
