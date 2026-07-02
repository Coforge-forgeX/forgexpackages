"""
GitHub Client Manager

Thread-safe, async-compatible GitHub client manager with TTL cache.
"""

from .github_client_for_llm import GitHubLLMWrapper as GitHub
from typing import Optional
import logging
from cachetools import TTLCache
import asyncio
from threading import Lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github_client_manager")


class GitHubClientManagerAsync:
    """
    Thread-safe, async-compatible GitHub client manager using TTL cache.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize the GitHub client manager.
        
        Args:
            config_manager: Manager instance for getting user configuration.
        """
        self.config_manager = config_manager
        self.client_cache = TTLCache(maxsize=1000, ttl=900)  # 15 minutes TTL
        self.lock = Lock()

    async def _fetch_credentials(self, workspace_id: str, user_id: str, conversation_id: str) -> Optional[list]:
        """
        Fetch GitHub credentials from user configuration.
        
        Args:
            workspace_id: Workspace identifier
            user_id: User identifier
            conversation_id: Conversation identifier
            
        Returns:
            List containing [token, repo_full_name, branch_name]
        """
        if not self.config_manager:
            raise ValueError("config_manager not provided to GitHubClientManagerAsync")
        
        try:
            loop = asyncio.get_event_loop()
            user_github_config = await loop.run_in_executor(
                None,
                self.config_manager.get_config,
                workspace_id,
                user_id
            )
            logger.debug(f"user_github_config: {user_github_config}")
            
            # Check if GitHub is explicitly disabled by user
            if not user_github_config.get("github_active", None):
                raise Exception("GitHub integration is disabled by user configuration.")
            
            # Get credentials from user config
            token = user_github_config.get("github_token")
            repo_full_name = user_github_config.get("github_repo_full_name")
            branch_name = user_github_config.get("github_branch")
            
            # Validate that we have credentials
            if not token or not repo_full_name:
                raise ValueError("GitHub configuration is incomplete or missing. Please set 'github_token' and 'github_repo_full_name' in user config.")
            
            logging.info(f"GitHub credentials fetched for user {user_id}")
            return [token, repo_full_name, branch_name]
        except Exception as e:
            logging.error(f"Error fetching GitHub credentials: {e}")
            raise

    async def _create_client(self, user_id: str, token: str, github_repo_full_name: str, branch_name: Optional[str] = None) -> Optional[GitHub]:
        """
        Create a new GitHub client instance.
        
        Args:
            user_id: User identifier for logging
            token: GitHub Personal Access Token
            github_repo_full_name: Full repository name (owner/repo)
            branch_name: Optional branch name
            
        Returns:
            GitHub client instance or None on failure
        """
        try:
            loop = asyncio.get_event_loop()
            client = await loop.run_in_executor(
                None,
                lambda: GitHub(
                    token=token,
                    github_repo_full_name=github_repo_full_name,
                    branch_name=branch_name
                )
            )
            logging.info(f"GitHub client created for repo:{github_repo_full_name} user: {user_id}")
            
            # Test the client connection
            client.myself()
            return client
        except Exception as e:
            logging.error(f"Failed to create GitHub client for repo {github_repo_full_name} user:{user_id}: {e}")
            if hasattr(e, 'status') and e.status == 401:
                raise Exception("Your Access Token has expired. Kindly renew and try again.")
            return None

    async def get_client(self, workspace_id: str, user_id: str, conversation_id: str) -> Optional[GitHub]:
        """
        Get or create a GitHub client for the specified user.
        
        Args:
            workspace_id: Workspace identifier
            user_id: User identifier
            conversation_id: Conversation identifier
            
        Returns:
            GitHub client instance
        """
        try:
            result = await self._fetch_credentials(workspace_id, user_id, conversation_id)
            token, github_repo_full_name, branch_name = result
        except Exception as e:
            logging.error(f"Error fetching GitHub credentials: {e}")
            raise
        
        with self.lock:
            if token in self.client_cache:
                logging.info(f"Using cached GitHub client for user:{user_id}")
                return self.client_cache[token]
        
        try:
            client = await self._create_client(user_id, token, github_repo_full_name, branch_name)
            if client:
                with self.lock:
                    self.client_cache[token] = client
                return client
            else:
                raise Exception("Unable to access Github, kindly check your credentials and try again.")
        except Exception as e:
            logging.error(f"Error getting GitHub client for user:{user_id}: {e}")
            raise

    def invalidate_cache(self, token: str) -> None:
        """
        Remove a client from the cache.
        
        Args:
            token: The token key to remove from cache
        """
        with self.lock:
            if token in self.client_cache:
                del self.client_cache[token]
                logging.info("GitHub client removed from cache")
