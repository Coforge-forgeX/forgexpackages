"""
GitHub Tools Helper

Provides reusable tool collection functions that any agent can use.
"""

from .github_client_for_llm import GitHubLLMWrapper as GitHub


def get_github_tools(github_client: GitHub) -> list:
    """
    Dynamically fetch tools from github_client that are marked with @agent_tool decorator.
    
    Only methods decorated with @agent_tool will be available to the agent.
    All other methods are for external use only.
    
    Args:
        github_client: An instance of GitHubLLMWrapper
        
    Returns:
        list: List of callable tool methods marked for the agent
    """
    tools = []
    
    # Iterate through all attributes of the github_client instance
    for attr_name in dir(github_client):
        # Skip private/protected methods
        if attr_name.startswith('_'):
            continue
        
        attr = getattr(github_client, attr_name)
        
        # Only include callable attributes (methods)
        if not callable(attr):
            continue
        
        # Get the underlying function to check for decorator
        # For bound methods, __func__ gives the function object
        func = getattr(attr, '__func__', attr)
        
        # Only include if marked with @agent_tool decorator
        if hasattr(func, '_is_agent_tool') and func._is_agent_tool:
            tools.append(attr)
    
    return tools
