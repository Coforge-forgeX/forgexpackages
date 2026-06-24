# from atlassian import Jira
from .jira_client_for_llm import JiraLLMWrapper as Jira
# from jira import JIRA
from typing import Optional
import logging
from cachetools import TTLCache
import asyncio
from threading import Lock
import json

logging.basicConfig(level=logging.INFO)

class JiraClientManagerAsync:
    """
    Thread-safe, async-compatible Jira client manager using Redis and TTL cache.
    """

    def __init__(self, redis_client = None, config_manager = None ):
        # self.redis_client = redis_client
        self.config_manager = config_manager
        self.client_cache = TTLCache(maxsize=1000, ttl=900)  # 15 minutes TTL
        self.lock = Lock()

    async def _fetch_credentials(self,workspace_id: str , user_id:str , conversation_id: str) -> Optional[str]:
        
        if not self.config_manager:
                raise ValueError("config_manager not provided to JiraClientManagerAsync")
            
        try:
            
            loop = asyncio.get_event_loop()
            
            # Run the synchronous get_config call in a thread pool
            user_jira_config = await loop.run_in_executor(
                None,
                self.config_manager.get_config,
                workspace_id,
                user_id
            )
            
            print("user_jira_config:",user_jira_config)
            
            if not user_jira_config.get("jira_active",True):
                raise Exception("Jira integration is not enabled for you.")
            elif "jira_access_token" not in user_jira_config or "jira_email" not in user_jira_config or "jira_url" not in user_jira_config: 
                raise ValueError("Jira configuration is incomplete or missing.")
            

            email = user_jira_config.get("jira_email",str)
            token = user_jira_config.get("jira_access_token",str)
            jira_url = user_jira_config.get("jira_url",str)
            return [email , token , jira_url]
        except Exception as e:  
            logging.error(f"Error fetching Jira credentials from Redis: {e}")
            raise

    async def _create_client(self,jira_url:str, email: str, token: str) -> Optional[Jira]:
        try:
            loop = asyncio.get_event_loop()
            client = await loop.run_in_executor(
                None,  # Uses default ThreadPoolExecutor
                lambda: Jira(
                    url=jira_url,
                    username=email,
                    password=token,
                    cloud=True
                )
            )
            # options = {'server': jira_url}
            # client = JIRA(options, basic_auth=(email, token))
            logging.info(f"Jira client created for {email}")
            client.myself()
            return client
        except Exception as e:
            logging.error(f"Failed to create Jira client for {email}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 401:
                # Unauthorized request
                raise Exception('Your Access Token has expired. Kindly renew and try again.')
                
            return None

    async def get_client(self,workspace_id: str , user_id:str ,conversation_id: str ) -> Optional[Jira]:
        
        try:
            
            result = await self._fetch_credentials(workspace_id , user_id , conversation_id)
            email, token , jira_url = result     
        except Exception as e:
            logging.error(f"Error fetching jira credentials: {e}")
            raise
        
        with self.lock:
            if email in self.client_cache:
                logging.info(f"Using cached Jira client for {email}")
                return self.client_cache[email]
        try:
            client = await self._create_client(jira_url, email, token)

            if client:
                with self.lock:
                    self.client_cache[email] = client
                return client
            else:
                raise Exception("Unable to access jira, kindly check your credentials and try again.")
        except Exception as e:
            logging.error(f"Error getting Jira client for {email}: {e}")
            raise