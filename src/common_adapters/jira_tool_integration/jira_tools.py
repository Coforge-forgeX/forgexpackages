"""
JIRA Tools Helper

Provides reusable tool collection functions that any agent can use.
"""

from .jira_client_for_llm import JiraLLMWrapper as Jira


def get_jira_tools(jira_client: Jira) -> list:
    """
    Get a comprehensive list of JIRA tools from a client instance.
    
    Args:
        jira_client: An instance of JIRALLMWrapper
        
    Returns:
        list: List of bound methods that can be used as LangChain tools
    """
    return [
        jira_client.get_issue_transitions_full,
        jira_client.get_issue_status,
        jira_client.get_transition_id_to_status_name,
        jira_client.set_issue_status_by_transition_id,
        jira_client.get_issue_status_changelog,
        jira_client.issue_get_watchers,
        jira_client.get_all_assignable_users_for_project,
        jira_client.assign_issue,
        jira_client.create_issue_link,
        jira_client.add_issues_to_sprint,
        jira_client.issue_editmeta,
        jira_client.issue_update,
        jira_client.create_issue,
        jira_client.issue_createmeta_issuetypes,
        jira_client.issue_createmeta_fieldtypes,
        jira_client.myself ,
        jira_client.get_project ,
        jira_client.get_issue ,
        jira_client.projects , 
        jira_client.get_all_project_issues ,
        jira_client.get_all_agile_boards , 
        jira_client.get_agile_board , 
        jira_client.get_all_sprints_from_board,
        jira_client.get_all_issues_for_sprint_in_board] 
