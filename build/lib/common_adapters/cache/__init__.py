"""
Cache module for managing Redis cache implementations.

This module provides a factory pattern for creating cache instances
based on the configured provider (Azure or AWS).

Usage:
    from cache import CacheFactory

    # Initialize the factory (should be done once at startup)
    CacheFactory.initialize()

    # Get a cache instance
    cache = CacheFactory.get_cache(prefix="myapp:")

    # Use the cache
    await cache.store_data({"key": "value"})
    result = await cache.retrieve_data("key")
"""

from .cache_factory import CacheFactory
from .base_cache import BaseCache
from .config import CacheConfig
from .redis_cache import AzureRedisCache
from .aws_elastic_cache import AWSElasticCache

__all__ = [
    "CacheFactory",
    "BaseCache",
    "CacheConfig",
    "AzureRedisCache",
    "AWSElasticCache",
]
