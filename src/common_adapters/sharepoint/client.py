import os
import logging
from typing import Optional
import msal
import requests

logger = logging.getLogger(__name__)

class SharePointClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, site_hostname: str, site_path: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.site_hostname = site_hostname
        self.site_path = site_path
        self.access_token = None
        self.site_id = None
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.app = msal.ConfidentialClientApplication(
            client_id,
            authority=self.authority,
            client_credential=client_secret
        )

    def authenticate(self) -> bool:
        try:
            result = self.app.acquire_token_for_client(scopes=self.scope)
            if "access_token" in result:
                self.access_token = result["access_token"]
                logger.info("Successfully authenticated with Microsoft Graph API")
                return True
            else:
                logger.error(f"Authentication failed: {result.get('error_description')}")
                return False
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False

    def _ensure_authenticated(self):
        if not self.access_token:
            self.authenticate()

    def get_site_id(self) -> Optional[str]:
        self._ensure_authenticated()
        try:
            site_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_hostname}:{self.site_path}"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(site_url, headers=headers)
            response.raise_for_status()
            site_data = response.json()
            self.site_id = site_data.get('id')
            logger.info(f"Retrieved site ID: {self.site_id}")
            return self.site_id
        except Exception as e:
            logger.error(f"Error getting site ID: {str(e)}")
            return None

    def get_headers(self):
        self._ensure_authenticated()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
