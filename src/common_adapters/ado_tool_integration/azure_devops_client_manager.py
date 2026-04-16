# from azure.devops.connection import Connection
from .azure_devops_client_for_llm import AzureDevOpsLLMWrapper as AzureDevOps
from typing import Optional, Callable, Any
# from cache.redis_cache import RedisCache
import logging
from cachetools import TTLCache
import asyncio
from threading import Lock
import json

logging.basicConfig(level=logging.INFO)

class AzureDevOpsClientManagerAsync:
    """
    Thread-safe, async-compatible Azure DevOps client manager using TTL cache.
    
    This manager is designed to be reusable across different agents by accepting
    a config_manager that can fetch user configuration.
    """

    def __init__(self, redis_client=None, config_manager=None):
        """
        Initialize the Azure DevOps client manager.
        
        Args:
            redis_client: Optional Redis client (kept for backwards compatibility)
            config_manager: Object with get_config(workspace_id, user_id) method
        """
        # self.redis_client = redis_client
        self.config_manager = config_manager
        self.client_cache = TTLCache(maxsize=1000, ttl=900)  # 15 minutes TTL
        self.lock = Lock()

    async def _fetch_credentials(self, workspace_id: str, user_id: str, conversation_id: str) -> Optional[list]:
        
        try:
            if not self.config_manager:
                raise ValueError("config_manager not provided to AzureDevOpsClientManagerAsync")
            
            loop = asyncio.get_event_loop()
            
            # Run the synchronous get_config call in a thread pool
            user_azure_devops_config = await loop.run_in_executor(
                None,
                self.config_manager.get_config,
                workspace_id,
                user_id
            )
            
            print("user_azure_devops_config:", user_azure_devops_config)
            
            if not user_azure_devops_config.get("azure_devops_active", None):
                raise Exception("Azure DevOps integration is not enabled for you.")
            elif ("azure_devops_access_token" not in user_azure_devops_config or 
                  "azure_devops_organization" not in user_azure_devops_config or 
                  "azure_devops_project" not in user_azure_devops_config): 
                raise ValueError("Azure DevOps configuration is incomplete or missing.")
            

            access_token = user_azure_devops_config.get("azure_devops_access_token")
            organization = user_azure_devops_config.get("azure_devops_organization")
            project = user_azure_devops_config.get("azure_devops_project")
            base_url = user_azure_devops_config.get("azure_devops_url", f"https://dev.azure.com/{organization}")
            
            return [access_token, organization, project, base_url]
        except Exception as e:  
            logging.error(f"Error fetching Azure DevOps credentials from Redis: {e}")
            raise

    async def _create_client(self, base_url: str, access_token: str, organization: str, project: str, user_id: str) -> Optional[AzureDevOps]:
        try:
            loop = asyncio.get_event_loop()
            client = await loop.run_in_executor(
                None,  # Uses default ThreadPoolExecutor
                lambda: AzureDevOps(
                    base_url=base_url,
                    access_token=access_token,
                    organization=organization,
                    project=project
                )
            )
            logging.info(f"Azure DevOps client created for organization: {organization}, project: {project} user: {user_id}")
            return client
        except Exception as e:
            logging.error(f"Failed to create Azure DevOps client for {organization}/{project} user: {user_id}: {e}")
            return None

    async def get_client(self, workspace_id: str, user_id: str, conversation_id: str) -> Optional[AzureDevOps]:
        
        try:
            
            result = await self._fetch_credentials(workspace_id, user_id, conversation_id)
            access_token, organization, project, base_url = result     
        except Exception as e:
            logging.error(f"Error fetching Azure DevOps credentials: {e}")
            raise
        
        cache_key = f"{user_id}_{organization}_{project}"

        
        with self.lock:
            if cache_key in self.client_cache:
                logging.info(f"Using cached Azure DevOps client for {user_id} {organization}/{project}")
                return self.client_cache[cache_key]
        try:
            client = await self._create_client(base_url, access_token, organization, project, user_id)

            if client:
                with self.lock:
                    self.client_cache[cache_key] = client
            return client
        except Exception as e:
            logging.error(f"Error getting Azure DevOps client for {user_id}{organization}/{project}: {e}")
            raise