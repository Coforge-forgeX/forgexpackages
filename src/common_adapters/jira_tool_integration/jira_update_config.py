
def azure_devops_update_config(data):
        """
        azure_devops_organization: your-azure-devops-organization,
        azure_devops_project: your-azure-devops-project,
        azure_devops_access_token: your-azure-devops-personal-access-token,
        azure_devops_area_path: your-azure-devops-area-path (optional),
        azure_devops_iteration_path: your-azure-devops-iteration-path (optional)
     # determine if azure devops is active based on the presence of azure devops fields
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