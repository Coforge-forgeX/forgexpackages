def github_update_config(data):
    """
    Update GitHub configuration based on provided data.
    
    Args:
        data: Dictionary containing GitHub configuration fields:
            - github_token: Personal Access Token for GitHub API
            - github_repo_full_name: Full repository name (e.g., 'owner/repo')
            - github_branch: Branch name (optional, defaults to main)
            
    Returns:
        Updated data dictionary with github_active flag set appropriately.
    """
    github_active = (
        data.get("github_token") is not None and 
        data.get("github_repo_full_name") is not None
    )
    
    if github_active:
        data["github_active"] = True
    else:
        data["github_active"] = False
    
    return data
