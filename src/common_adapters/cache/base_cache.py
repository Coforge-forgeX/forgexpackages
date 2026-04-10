from abc import ABC, abstractmethod


class BaseCache(ABC):
    """
    Abstract base class for cache implementations.
    All cache implementations should inherit from this class and implement the required methods.
    """

    def __init__(self, prefix: str):
        """
        Initialize the cache with a prefix for keys.

        Args:
            prefix (str): The prefix to be added to all cache keys.
        """
        self.prefix = prefix

    @abstractmethod
    async def append_to_key(self, data: dict) -> dict:
        """
        Append data to a Redis key.

        Args:
            data (dict): A dictionary containing the key and value to append.

        Returns:
            dict: Confirmation of the append operation.
        """
        pass

    @abstractmethod
    async def store_data(self, data: dict) -> dict:
        """
        Store data in cache. Expiry time set to 15mins.

        Args:
            data (dict): Dictionary of key-value pairs to store.

        Returns:
            dict: Confirmation of storage.
        """
        pass

    @abstractmethod
    async def retrieve_data(self, key: str | list[str]) -> dict:
        """
        Retrieve data from cache.

        Args:
            key (str | list[str]): The key or list of keys to retrieve values for.

        Returns:
            dict: The value stored under the key, or an error message if not found.
        """
        pass

    @abstractmethod
    async def get_all(self, uuid: str | None = None) -> dict:
        """
        Retrieve all keys or keys for uuid and their values from cache.

        Args:
            uuid (str | None): Optional UUID to filter keys. If provided, only keys starting with the UUID will be returned.

        Returns:
            dict: A dictionary containing all keys and their corresponding values.
        """
        pass

    @abstractmethod
    async def flush_all(self, uuid: str | None = None) -> dict:
        """
        Flush all data from cache or data relevant to provided uuid.

        Args:
            uuid (str | None): Optional UUID to filter keys. If provided, only keys matching the UUID will be deleted.

        Returns:
            dict: Confirmation of the flush operation.
        """
        pass
