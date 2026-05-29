import asyncio
import logging
from threading import Lock
from typing import Optional

from cachetools import TTLCache

from .client import SharePointClient

logger = logging.getLogger(__name__)


def _get_loop() -> asyncio.AbstractEventLoop:
    """Return the running loop; fall back to asyncio.get_event_loop() on older runtimes."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop()

class SharePointClientManagerAsync:
    """
    Thread-safe, async-compatible SharePoint client manager using TTL cache.
    
    This manager is designed to be reusable across different agents by accepting
    a config_manager that can fetch user configuration.
    """

    def __init__(self, redis_client=None, config_manager=None):
        """
        Initialize the SharePoint client manager.
        
        Args:
            redis_client: Optional Redis client (kept for backwards compatibility)
            config_manager: Object with get_config(workspace_id, user_id) method
        """
        # self.redis_client = redis_client
        self.config_manager = config_manager
        self.client_cache = TTLCache(maxsize=1000, ttl=900)  # 15 minutes TTL
        self.lock = Lock()

    async def _fetch_credentials(self, workspace_id: str, user_id: str, conversation_id: str) -> list:
        if not self.config_manager:
            raise ValueError("config_manager not provided to SharePointClientManagerAsync")
        loop = _get_loop()
        user_sharepoint_config = await loop.run_in_executor(
            None,
            self.config_manager.get_config,
            workspace_id,
            user_id,
        )
        if not user_sharepoint_config:
            raise ValueError("SharePoint configuration not found for user.")
        if not user_sharepoint_config.get("sharepoint_active"):
            raise Exception("SharePoint integration is not enabled for you.")
        required_fields = ["tenant_id", "client_id", "client_secret", "site_hostname", "site_path"]
        if not all(user_sharepoint_config.get(f) for f in required_fields):
            raise ValueError("SharePoint configuration is incomplete or missing.")
        return [user_sharepoint_config[f] for f in required_fields]

    async def _create_client(self, tenant_id: str, client_id: str, client_secret: str, site_hostname: str, site_path: str, user_id: str) -> Optional[SharePointClient]:
        try:
            loop = _get_loop()
            client = await loop.run_in_executor(
                None,
                lambda: SharePointClient(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                    site_hostname=site_hostname,
                    site_path=site_path,
                ),
            )
            logger.info(f"SharePoint client created for site: {site_hostname}{site_path} user: {user_id}")
            return client
        except Exception as e:
            logger.error(f"Failed to create SharePoint client for {site_hostname}{site_path} user: {user_id}: {e}")
            return None

    async def get_client(self, workspace_id: str, user_id: str, conversation_id: str) -> Optional[SharePointClient]:
        try:
            tenant_id, client_id, client_secret, site_hostname, site_path = await self._fetch_credentials(
                workspace_id, user_id, conversation_id
            )
        except Exception as e:
            logger.error(f"Error fetching SharePoint credentials: {e}")
            raise
        cache_key = f"{user_id}_{tenant_id}_{site_hostname}"
        with self.lock:
            if cache_key in self.client_cache:
                logger.info(f"Using cached SharePoint client for {user_id} {site_hostname}{site_path}")
                return self.client_cache[cache_key]
        try:
            client = await self._create_client(tenant_id, client_id, client_secret, site_hostname, site_path, user_id)
            if client:
                with self.lock:
                    self.client_cache[cache_key] = client
            return client
        except Exception as e:
            logger.error(f"Error getting SharePoint client for {user_id} {site_hostname}{site_path}: {e}")
            raise
