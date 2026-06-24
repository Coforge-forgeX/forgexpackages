"""
JIRA Connection Management

This module provides standardized connection testing and toggling functionality
for jira integrations across all agents.
"""

import asyncio
import logging
from typing import Any
from .jira_client_for_llm import JiraLLMWrapper as Jira
from .jira_client_manager import JiraClientManagerAsync

logger = logging.getLogger(__file__)


async def test_jira_connection(workspace_id: str , user_id:str , data: dict[str,Any], jira_client_class: Jira, user_config_manager ) -> dict[str,Any]:
    """
    This tool tests the Jira connection for the given workspace and user.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        data (dict): dictionary containing jira_access_token, jira_email, jira_url.
        jira_client_class: The JIRA client class to instantiate.
        user_config_manager: Manager instance for getting user configuration.
    Returns:
        dict : dictionary containing the status of the connection test.
    """
    if user_id is None:
        return {"status": "error", "error": "user_id cannot be null"}
    
    try:
        
        loop = asyncio.get_event_loop()
        jira_client = await loop.run_in_executor(
            None,
            lambda: Jira(
                url=data['jira_url'],
                username=data['jira_email'],
                password=data['jira_access_token'],
                cloud=True
            )
        )
        # Test the connection by fetching projects
        jira_client.myself()
        
        # fetch user config
        try:
            user_config = user_config_manager.get_config(workspace_id , user_id ,["jira_url","jira_email","jira_access_token"] )
            exists = all(user_config.get(k)== v for k,v in data.items())
        except Exception as e:
            logger.error(f"Error fetching user config during Jira connection test: {e}")
            return {"status":"error","message":f"Unable to fetch jira config {e}"}
        return {"status":"success","message":"Jira connection successful.","exists":exists}
    except Exception as e:
        logger.error(f"Error testing Jira connection: {e}")
        return {"status":"error","message":"Please check your JIRA credentials and try again."}
    
    
async def toggle_jira_connection(workspace_id: str , user_id: str , enable: bool , jira_client_manager: JiraClientManagerAsync , user_config_manager ) -> dict[str,Any]:
    """
    This tool enables or disables the Jira connection for the given workspace and user.
    
    Args:
        workspace_id (str): unique identifier for the workspace.
        user_id (str): unique identifier for the user.
        enable (bool): flag to enable or disable the connection.
        jira_client_manager: Manager instance for JIRA clients.
        user_config_manager: Manager instance for user configuration.
        
    Returns:
        dict : dictionary containing the status of the operation.
    """
    
    if user_id is None:
        return {"status": "error", "error": "user_id cannot be null"}
    
    try:
        # remove jira_client from the jira_client_manager cache if disabling
        if not enable:
            with jira_client_manager.lock:
                user_jira_config = user_config_manager.get_config(workspace_id , user_id )
                email = user_jira_config.get("jira_email",str)
                if email in jira_client_manager.client_cache:
                    del jira_client_manager.client_cache[email]
        
        user_config_manager.set_config(workspace_id, user_id, {"jira_active": enable})
        status_msg = "enabled" if enable else "disabled"
        return {"status":"success","message":f"Jira connection {status_msg} successfully."}
    except Exception as e:
        logger.error(f"Error toggling Jira connection: {e}")
        return {"status":"error","message":str(e)}