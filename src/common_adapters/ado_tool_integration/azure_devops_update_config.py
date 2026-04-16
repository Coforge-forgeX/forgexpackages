def azure_devops_update_config(data):
        """
        azure_devops_organization: your-azure-devops-organization,
        azure_devops_project: your-azure-devops-project,
        azure_devops_access_token: your-azure-devops-personal-access-token,
        azure_devops_area_path: your-azure-devops-area-path (optional),
        azure_devops_iteration_path: your-azure-devops-iteration-path (optional)
     # determine if azure devops is active based on the presence of azure devops fields
     """
        azure_devops_active = (
            data.get("azure_devops_organization") is not None and 
            data.get("azure_devops_project") is not None and 
            data.get("azure_devops_access_token") is not None and
            data.get("azure_devops_url") is not None
        )
        if azure_devops_active:
            data["azure_devops_active"] = True
        else:
            data["azure_devops_active"] = False
        return data