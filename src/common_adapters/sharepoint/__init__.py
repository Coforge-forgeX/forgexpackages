"""SharePoint integration package.

Public surface:
    SharePointClient                 - low-level Graph API client (auth + site id)
    SharePointService                - file listing, download, metadata-filtered extraction
    SharePointClientManagerAsync     - cached per-user client manager for multi-agent use
    test_sharepoint_connection       - verify a user's SharePoint credentials
    toggle_sharepoint_connection     - enable/disable SharePoint for a user (clears cache)
    sharepoint_update_config         - normalize a config dict and set ``sharepoint_active``
"""

from .client import SharePointClient
from .service import SharePointService
from .sharepoint_client_manager import SharePointClientManagerAsync
from .sharepoint_connection import (
    test_sharepoint_connection,
    toggle_sharepoint_connection,
)
from .sharepoint_update_config import sharepoint_update_config

__all__ = [
    "SharePointClient",
    "SharePointService",
    "SharePointClientManagerAsync",
    "test_sharepoint_connection",
    "toggle_sharepoint_connection",
    "sharepoint_update_config",
]

__version__ = "1.0.0"
