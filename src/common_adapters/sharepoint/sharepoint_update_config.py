def sharepoint_update_config(data):
    """
    tenant_id: your-tenant-id,
    client_id: your-client-id,
    client_secret: your-client-secret,
    site_hostname: your-site-hostname,
    site_path: your-site-path
    # determine if sharepoint is active based on the presence of required sharepoint fields
    """
    sharepoint_active = (
        data.get("tenant_id") is not None and
        data.get("client_id") is not None and
        data.get("client_secret") is not None and
        data.get("site_hostname") is not None and
        data.get("site_path") is not None
    )
    if sharepoint_active:
        data["sharepoint_active"] = True
    else:
        data["sharepoint_active"] = False
    return data
