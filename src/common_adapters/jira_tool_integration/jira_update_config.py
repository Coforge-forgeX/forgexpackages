
def jira_update_config(data):
    """
        jira_access_token: You PAT token for jira client creation.
        jira_email: your email account on jira
        jira_url: project url of you jira project(example: https://your-jira_project.atlassian.net/)
        # determine if jira is active based on the presence of jira fields
     """
            
    jira_active = (
        data.get("jira_access_token") is not None and 
        data.get("jira_email") is not None and 
        data.get("jira_url") is not None
    )
    
    if jira_active:
        data["jira_active"] = True
    else:
        data["azure_devops_active"] = False
    return data