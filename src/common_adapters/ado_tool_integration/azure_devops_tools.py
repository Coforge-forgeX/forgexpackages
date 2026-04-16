"""
Azure DevOps Tools Helper

Provides reusable tool collection functions that any agent can use.
"""

from .azure_devops_client_for_llm import AzureDevOpsLLMWrapper


def get_azure_devops_tools(azure_devops_client: AzureDevOpsLLMWrapper) -> list:
    """
    Get a comprehensive list of Azure DevOps tools from a client instance.
    
    Args:
        azure_devops_client: An instance of AzureDevOpsLLMWrapper
        
    Returns:
        list: List of bound methods that can be used as LangChain tools
    """
    return [
        # Work Item Management
        azure_devops_client.create_work_item,
        azure_devops_client.update_work_item,
        azure_devops_client.get_work_item,
        azure_devops_client.get_work_items_by_query,
        azure_devops_client.get_work_items_by_ids,
        azure_devops_client.search_work_items,
        azure_devops_client.get_work_items_by_assignee,
        azure_devops_client.assign_work_item,
        azure_devops_client.update_work_item_state,
        azure_devops_client.get_board_users,
        azure_devops_client.get_board_user,
        
        # Work Item Metadata
        azure_devops_client.get_work_item_types,
        azure_devops_client.get_work_item_fields,
        azure_devops_client.get_work_item_states,
        azure_devops_client.get_work_item_transitions,
        
        # Work Item Relations and Links
        azure_devops_client.create_work_item_link,
        
        # Work Item History and Comments
        azure_devops_client.get_work_item_revisions,
        azure_devops_client.get_work_item_comments,
        azure_devops_client.add_work_item_comment,
        azure_devops_client.get_work_item_attachments,
        
        # Team Management
        azure_devops_client.get_teams,
        
        # Board Management
        azure_devops_client.get_team_boards,
        azure_devops_client.get_board,
        azure_devops_client.get_board_columns,
        azure_devops_client.get_board_rows,
        
        # Sprint/Iteration Management
        azure_devops_client.get_team_iterations,
        azure_devops_client.get_iteration,
        azure_devops_client.get_iteration_work_items,
        azure_devops_client.add_work_items_to_iteration,
        
        # Capacity Management
        azure_devops_client.get_team_capacity,
        azure_devops_client.update_team_member_capacity,
        
        # Project Structure
        azure_devops_client.get_project_areas,
        azure_devops_client.get_project_iterations,
        azure_devops_client.get_project_info,
        
        # User Information
        azure_devops_client.get_current_user
    ]
