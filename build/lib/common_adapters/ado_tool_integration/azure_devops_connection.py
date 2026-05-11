"""
Azure DevOps Connection Management

This module provides standardized connection testing and toggling functionality
for Azure DevOps integrations across all agents.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger("azure_devops_connection")


async def test_azure_devops_connection(
    workspace_id: str,
    user_id: str,
    data: dict[str, Any],
    azure_devops_client_class,
    user_config_manager
) -> dict[str, Any]:
    """
    Tests the Azure DevOps connection for the given workspace and user.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        data (dict): dictionary containing azure_devops_access_token, azure_devops_organization, 
                     azure_devops_project, azure_devops_url.
        azure_devops_client_class: The AzureDevOps client class to instantiate.
        user_config_manager: Manager instance for getting user configuration.
        
    Returns:
        dict: dictionary containing the status of the connection test.
    """
    if user_id is None:
        return {"status": "error", "error": "user_id cannot be null"}
    
    try:
        loop = asyncio.get_event_loop()
        azure_devops_client = await loop.run_in_executor(
            None,
            lambda: azure_devops_client_class(
                base_url=data['azure_devops_url'],
                access_token=data['azure_devops_access_token'],
                organization=data['azure_devops_organization'],
                project=data['azure_devops_project']
            )
        )
        
        # Test the connection by fetching current user info
        azure_devops_client.get_current_user()
        
        # fetch user config
        try:
            user_config = user_config_manager.get_config(
                workspace_id, 
                user_id, 
                ["azure_devops_url", "azure_devops_access_token", "azure_devops_organization", "azure_devops_project"]
            )
            exists = all(user_config.get(k) == v for k, v in data.items())
        except Exception as e:
            logger.error(f"Error fetching user config during Azure DevOps connection test: {e}")
            return {"status": "error", "message": f"Unable to fetch Azure DevOps config: {e}"}
        
        return {"status": "success", "message": "Azure DevOps connection successful.", "exists": exists}
    
    except Exception as e:
        logger.error(f"Error testing Azure DevOps connection: {e}")
        return {"status": "error", "message": "Please check your Azure DevOps credentials and try again."}


async def toggle_azure_devops_connection(
    workspace_id: str,
    user_id: str,
    enable: bool,
    azure_devops_client_manager,
    user_config_manager
) -> dict[str, Any]:
    """
    Enables or disables the Azure DevOps connection for the given workspace and user.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        enable (bool): flag to enable or disable the connection.
        azure_devops_client_manager: Manager instance for Azure DevOps clients.
        user_config_manager: Manager instance for user configuration.
        
    Returns:
        dict: dictionary containing the status of the operation.
    """
    if user_id is None:
        return {"status": "error", "error": "user_id cannot be null"}
    
    try:
        # remove azure_devops_client from the azure_devops_client_manager cache if disabling
        if not enable:
            with azure_devops_client_manager.lock:
                user_azure_devops_config = user_config_manager.get_config(workspace_id, user_id)
                organization = user_azure_devops_config.get("azure_devops_organization", str)
                project = user_azure_devops_config.get("azure_devops_project", str)
                cache_key = f"{user_id}_{organization}_{project}"
                if cache_key in azure_devops_client_manager.client_cache:
                    del azure_devops_client_manager.client_cache[cache_key]
        
        user_config_manager.set_config(workspace_id, user_id, {"azure_devops_active": enable})
        status_msg = "enabled" if enable else "disabled"
        return {"status": "success", "message": f"Azure DevOps connection {status_msg} successfully."}
    
    except Exception as e:
        logger.error(f"Error toggling Azure DevOps connection: {e}")
        return {"status": "error", "message": str(e)}
