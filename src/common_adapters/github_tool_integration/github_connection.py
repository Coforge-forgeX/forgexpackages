"""
GitHub Connection Management

This module provides standardized connection testing and toggling functionality
for GitHub integrations across all agents.
"""

import asyncio
import logging
from typing import Any
from .github_client_for_llm import GitHubLLMWrapper as GitHub
from .github_client_manager import GitHubClientManagerAsync

logger = logging.getLogger(__name__)


async def test_github_connection(workspace_id: str, user_id: str, data: dict[str, Any], 
                                  user_config_manager) -> dict[str, Any]:
    """
    Test the GitHub connection for the given workspace and user.
    If the test is successful, it can optionally save the credentials.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        data (dict): dictionary containing github_token, github_repo_full_name, and optionally github_branch.
        user_config_manager: Manager instance for user configuration.
        
    Returns:
        dict: dictionary containing the status of the connection test.
    """
    if user_id is None:
        return {"status": "error", "message": "user_id cannot be null"}
    
    try:
        logger.info(f"Testing GitHub connection for user_id={user_id}, workspace_id={workspace_id}, repo={data.get('github_repo_full_name')}")
        
        branch = data.get('github_branch', 'main')
        
        loop = asyncio.get_event_loop()
        github_tool = await loop.run_in_executor(
            None,
            lambda: GitHub(
                token=data['github_token'],
                github_repo_full_name=data['github_repo_full_name'],
                branch_name=branch
            )
        )
        
        # Test the connection by verifying repo access and branch availability
        try:
            repo_branch = github_tool._repo.get_branch(branch)
            logger.info(f"GitHub connection test successful for user_id={user_id}, workspace_id={workspace_id}, branch={repo_branch.name}")
        except Exception as e:
            error_msg = str(e)
            if any(auth_err in error_msg.lower() for auth_err in ["401", "403", "bad credentials", "unauthorized", "forbidden"]):
                logger.error(f"GitHub authentication failed for user_id={user_id}: {e}")
                return {"status": "error", "message": "Invalid GitHub token or insufficient permissions. Please check your credentials and try again."}
            logger.error(f"Error verifying GitHub repository access for user_id={user_id}: {e}")
            return {"status": "error", "message": f"Error connecting to GitHub: {e}"}
        
        # Check if credentials already exist
        try:
            user_config = user_config_manager.get_config(workspace_id, user_id, ["github_token", "github_repo_full_name", "github_branch"])
            exists = all(user_config.get(k) == v for k, v in data.items() if k in user_config)
        except Exception as e:
            logger.error(f"Error fetching user config during GitHub connection test: {e}")
            exists = False
        
        return {"status": "success", "message": "GitHub connection successful.", "exists": exists}
    except Exception as e:
        logger.error(f"Error testing GitHub connection for user_id={user_id}: {e}")
        return {"status": "error", "message": "Please check your GitHub credentials and try again."}


async def save_github_credentials(workspace_id: str, user_id: str, data: dict[str, Any],
                                   user_config_manager) -> dict[str, Any]:
    """
    Save GitHub credentials after a successful connection test.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        data (dict): dictionary containing github_token, github_repo_full_name, and optionally github_branch.
        user_config_manager: Manager instance for user configuration.
        
    Returns:
        dict: dictionary containing the status of the save operation.
    """
    try:
        # Prepare config data
        config_data = {
            "github_token": data['github_token'],
            "github_repo_full_name": data['github_repo_full_name'],
            "github_branch": data.get('github_branch', 'main'),
            "github_active": True
        }
        
        logger.info(f"Saving GitHub credentials for user_id={user_id}, workspace_id={workspace_id}")
        user_config_manager.set_config(workspace_id, user_id, config_data)
        
        # Verify credentials were saved
        saved_config = user_config_manager.get_config(workspace_id, user_id, ["github_token", "github_repo_full_name", "github_branch", "github_active"])
        logger.info(f"Verified saved GitHub config for user_id={user_id}: token={'***' if saved_config.get('github_token') else None}, repo={saved_config.get('github_repo_full_name')}, active={saved_config.get('github_active')}")
        
        return {"status": "success", "message": "GitHub credentials saved successfully."}
    except Exception as e:
        logger.error(f"Error saving GitHub credentials for user_id={user_id}: {e}")
        return {"status": "error", "message": f"Failed to save credentials: {e}"}


async def test_and_save_github_connection(workspace_id: str, user_id: str, data: dict[str, Any],
                                           user_config_manager) -> dict[str, Any]:
    """
    Test the GitHub connection and save credentials if successful.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        data (dict): dictionary containing github_token, github_repo_full_name, and optionally github_branch.
        user_config_manager: Manager instance for user configuration.
        
    Returns:
        dict: dictionary containing the status of the operation.
    """
    # First test the connection
    test_result = await test_github_connection(workspace_id, user_id, data, user_config_manager)
    
    if test_result.get("status") != "success":
        return test_result
    
    # If test successful, save the credentials
    save_result = await save_github_credentials(workspace_id, user_id, data, user_config_manager)
    
    if save_result.get("status") != "success":
        return {"status": "error", "message": f"Connection successful but failed to save credentials: {save_result.get('message')}"}
    
    return {"status": "success", "message": "GitHub connection successful and credentials saved."}


async def toggle_github_connection(workspace_id: str, user_id: str, enable: bool,
                                    github_client_manager: GitHubClientManagerAsync,
                                    user_config_manager) -> dict[str, Any]:
    """
    Enable or disable the GitHub connection for the given workspace and user.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        enable (bool): flag to enable or disable the connection.
        github_client_manager: Manager instance for GitHub clients.
        user_config_manager: Manager instance for user configuration.
        
    Returns:
        dict: dictionary containing the status of the operation.
    """
    if user_id is None:
        return {"status": "error", "message": "user_id cannot be null"}
    
    try:
        # Remove github_client from the cache if disabling
        if not enable:
            user_github_config = user_config_manager.get_config(workspace_id, user_id)
            token = user_github_config.get("github_token")
            if token and github_client_manager:
                github_client_manager.invalidate_cache(token)
        
        user_config_manager.set_config(workspace_id, user_id, {"github_active": enable})
        status_msg = "enabled" if enable else "disabled"
        return {"status": "success", "message": f"GitHub connection {status_msg} successfully."}
    except Exception as e:
        logger.error(f"Error toggling GitHub connection: {e}")
        return {"status": "error", "message": str(e)}
