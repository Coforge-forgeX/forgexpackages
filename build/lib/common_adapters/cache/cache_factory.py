from typing import Optional
from .config import CacheConfig
from .base_cache import BaseCache


class CacheFactory:
    """
    Factory class for creating cache instances based on the configured provider.
    """

    _config: Optional[CacheConfig] = None

    @classmethod
    def initialize(cls):
        """
        Initialize the cache factory by loading configuration from environment variables.
        This should be called once at application startup.
        """
        if cls._config is None:
            cls._config = CacheConfig()

    @classmethod
    def get_cache(cls, prefix: str = "") -> BaseCache:
        """
        Get a cache instance based on the REDIS_PROVIDER environment variable.

        Args:
            prefix (str): Optional prefix for cache keys.

        Returns:
            BaseCache: An instance of the appropriate cache implementation.

        Raises:
            ValueError: If the configured provider is not supported.
            RuntimeError: If the factory has not been initialized.
        """
        # Ensure config is initialized
        if cls._config is None:
            cls.initialize()

        provider = cls._config.get_provider()

        if provider == "azure":
            from .redis_cache import AzureRedisCache
            return AzureRedisCache(prefix)
        elif provider == "aws":
            from .aws_elastic_cache import AWSElasticCache
            return AWSElasticCache(prefix)
        else:
            raise ValueError(
                f"Unsupported cache provider: {provider}. "
                f"Supported providers are: 'azure', 'aws'"
            )

    @classmethod
    def reset(cls):
        """
        Reset the factory configuration.
        Useful for testing or when configuration needs to be reloaded.
        """
        cls._config = None
