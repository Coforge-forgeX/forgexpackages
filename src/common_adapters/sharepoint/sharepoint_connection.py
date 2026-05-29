"""
SharePoint Connection Management

This module provides standardized connection testing and toggling functionality
for SharePoint integrations across all agents.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger("sharepoint_connection")


async def test_sharepoint_connection(
    workspace_id: str,
    user_id: str,
    data: dict[str, Any],
    sharepoint_client_class,
    user_config_manager
) -> dict[str, Any]:
    """
    Tests the SharePoint connection for the given workspace and user.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        data (dict): dictionary containing tenant_id, client_id, client_secret, site_hostname, site_path.
        sharepoint_client_class: The SharePoint client class to instantiate.
        user_config_manager: Manager instance for getting user configuration.
        
    Returns:
        dict: dictionary containing the status of the connection test.
    """
    if user_id is None:
        return {"status": "error", "error": "user_id cannot be null"}
    
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        sharepoint_client = await loop.run_in_executor(
            None,
            lambda: sharepoint_client_class(
                tenant_id=data['tenant_id'],
                client_id=data['client_id'],
                client_secret=data['client_secret'],
                site_hostname=data['site_hostname'],
                site_path=data['site_path']
            )
        )
        # Test the connection by authenticating and getting site id
        authenticated = sharepoint_client.authenticate()
        site_id = sharepoint_client.get_site_id() if authenticated else None
        if not authenticated or not site_id:
            return {"status": "error", "message": "SharePoint authentication or site retrieval failed."}
        # fetch user config
        try:
            user_config = user_config_manager.get_config(
                workspace_id, 
                user_id, 
                ["tenant_id", "client_id", "client_secret", "site_hostname", "site_path"]
            )
            exists = all(user_config.get(k) == v for k, v in data.items())
        except Exception as e:
            logger.error(f"Error fetching user config during SharePoint connection test: {e}")
            return {"status": "error", "message": f"Unable to fetch SharePoint config: {e}"}
        return {"status": "success", "message": "SharePoint connection successful.", "exists": exists}
    except Exception as e:
        logger.error(f"Error testing SharePoint connection: {e}")
        return {"status": "error", "message": "Please check your SharePoint credentials and try again."}


async def toggle_sharepoint_connection(
    workspace_id: str,
    user_id: str,
    enable: bool,
    sharepoint_client_manager,
    user_config_manager
) -> dict[str, Any]:
    """
    Enables or disables the SharePoint connection for the given workspace and user.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        enable (bool): flag to enable or disable the connection.
        sharepoint_client_manager: Manager instance for SharePoint clients.
        user_config_manager: Manager instance for user configuration.
        
    Returns:
        dict: dictionary containing the status of the operation.
    """
    if user_id is None:
        return {"status": "error", "error": "user_id cannot be null"}
    try:
        # remove sharepoint_client from the sharepoint_client_manager cache if disabling
        if not enable:
            with sharepoint_client_manager.lock:
                user_sharepoint_config = user_config_manager.get_config(workspace_id, user_id) or {}
                tenant_id = user_sharepoint_config.get("tenant_id", "")
                site_hostname = user_sharepoint_config.get("site_hostname", "")
                cache_key = f"{user_id}_{tenant_id}_{site_hostname}"
                if cache_key in sharepoint_client_manager.client_cache:
                    del sharepoint_client_manager.client_cache[cache_key]
        user_config_manager.set_config(workspace_id, user_id, {"sharepoint_active": enable})
        status_msg = "enabled" if enable else "disabled"
        return {"status": "success", "message": f"SharePoint connection {status_msg} successfully."}
    except Exception as e:
        logger.error(f"Error toggling SharePoint connection: {e}")
        return {"status": "error", "message": str(e)}
