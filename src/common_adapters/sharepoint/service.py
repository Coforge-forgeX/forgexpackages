import requests
from typing import List, Dict, Optional
from pathlib import Path
import logging
import os
from datetime import datetime
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)

class SharePointService:

    def __init__(self, client):
        self.client = client

    def get_data_from_file(self, content):
        """
        Extract text from file content using Azure Document Intelligence.
        Args:
            content: File content in bytes
        Returns:
            Extracted text content (str) or None if error
        """
        try:
            endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
            api_key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
            if not endpoint or not api_key:
                logger.error("Azure Document Intelligence endpoint or key not set in environment variables.")
                return None
            doc_client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(api_key))
            poller = doc_client.begin_analyze_document(
                "prebuilt-read",
                body=AnalyzeDocumentRequest(bytes_source=content),
                locale="en-US"
            )
            result = poller.result()
            return result.content
        except Exception as e:
            logger.error(f"Failed to process file with Document Intelligence: {e}")
            return None

    def _get_all_files_recursive(self, folder_path: str = "") -> List[Dict]:
        all_files = []
        if not self.client.site_id:
            self.client.get_site_id()
        try:
            if folder_path:
                folder_url = f"https://graph.microsoft.com/v1.0/sites/{self.client.site_id}/drive/root:{folder_path}:/children"
            else:
                folder_url = f"https://graph.microsoft.com/v1.0/sites/{self.client.site_id}/drive/root/children"
            headers = {"Authorization": f"Bearer {self.client.access_token}"}
            response = requests.get(folder_url, headers=headers)
            response.raise_for_status()
            items = response.json().get('value', [])
            for item in items:
                if 'folder' in item:
                    subfolder_path = f"{folder_path}/{item['name']}" if folder_path else item['name']
                    all_files.extend(self._get_all_files_recursive(subfolder_path))
                elif 'file' in item:
                    all_files.append(item)
        except Exception as e:
            logger.error(f"Error listing folder contents: {str(e)}")
        return all_files

    def list_files(self, folder_path: str = "") -> List[Dict]:
        return self._get_all_files_recursive(folder_path)

    def download_file(self, file_id: str) -> Optional[bytes]:
        self.client._ensure_authenticated()
        try:
            file_url = f"https://graph.microsoft.com/v1.0/sites/{self.client.site_id}/drive/items/{file_id}"
            headers = {"Authorization": f"Bearer {self.client.access_token}"}
            response = requests.get(file_url, headers=headers)
            response.raise_for_status()
            file_data = response.json()
            download_url = file_data.get('@microsoft.graph.downloadUrl')
            if not download_url:
                logger.error(f"No download URL for file ID: {file_id}")
                return None
            response = requests.get(download_url)
            response.raise_for_status()
            logger.info(f"Downloaded file ID {file_id} ({len(response.content)} bytes)")
            return response.content
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {str(e)}")
            return None

    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        self.client._ensure_authenticated()
        try:
            file_url = f"https://graph.microsoft.com/v1.0/sites/{self.client.site_id}/drive/items/{file_id}"
            headers = {"Authorization": f"Bearer {self.client.access_token}"}
            response = requests.get(file_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting file metadata: {str(e)}")
            return None
     # ---------------------- UNIFIED FILTER (METADATA + FILTERS) ----------------------
    def _should_process_file(self, file_item: Dict, metadata_map: Optional[Dict]) -> bool:
        """
        Only metadata-based filtering (global conditions like SharePoint metadata)
        """

        if not metadata_map:
            return True


        file_name = file_item.get('name', '')
        file_size = file_item.get('size', 0)
        extension = Path(file_name).suffix.lower()
        created = file_item.get('createdDateTime')
        modified = file_item.get('lastModifiedDateTime')
        # ✅ FILE TYPES (multiple allowed)
        if metadata_map.get("file_types"):
            if extension not in metadata_map["file_types"]:
                return False
        # ✅ NAME FILTER
        if metadata_map.get("name_contains"):
            if metadata_map["name_contains"].lower() not in file_name.lower():
                return False
        # ✅ SIZE FILTER
        if metadata_map.get("min_size"):
            if file_size < metadata_map["min_size"]:
                return False


        if metadata_map.get("max_size"):
            if file_size > metadata_map["max_size"]:
                return False


        # ✅ CREATED DATE FILTER
        if created:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))


            if metadata_map.get("created_after"):
                if created_dt < metadata_map["created_after"]:
                    return False


            if metadata_map.get("created_before"):
                if created_dt > metadata_map["created_before"]:
                    return False


        # ✅ MODIFIED DATE FILTER
        if modified:
            modified_dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))


            if metadata_map.get("modified_after"):
                if modified_dt < metadata_map["modified_after"]:
                    return False


            if metadata_map.get("modified_before"):
                if modified_dt > metadata_map["modified_before"]:
                    return False


        return True

    def extract_data(self, folder_path: str = "", metadata_map: Optional[Dict[str, Dict]] = None,):
        if not self.client.site_id:
            self.client.get_site_id()
        documents = []
        files = self._get_all_files_recursive(folder_path)
        logger.info(f"Found {len(files)} files to process")
        for file_item in files:
            try:
                file_id = file_item.get('id')
                file_name = file_item.get('name')
                # ✅ UNIFIED CHECK
                if metadata_map and not self._should_process_file(file_item, metadata_map):
                    logger.info(f"Skipped: {file_name}")
                    continue
                content = self.download_file(file_id)
                if not content:
                    logger.warning(f"Could not download {file_name}")
                    continue
                extension = Path(file_name).suffix.lower()
                text = None
                file_content = None
                try:
                    endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
                    api_key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
                    if not endpoint or not api_key:
                        logger.error("Azure Document Intelligence endpoint or key not set in environment variables.")
                    else:
                        doc_client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(api_key))
                        poller = doc_client.begin_analyze_document(
                            "prebuilt-read",
                            body=AnalyzeDocumentRequest(bytes_source=content),
                            locale="en-US"
                        )
                        result = poller.result()
                        file_content = result.content
                        text = file_content
                except Exception as e:
                    logger.error(f"Failed to process file with Document Intelligence: {e}")
                doc = {
                    'id': file_id,
                    'name': file_name,
                    'content': file_content,
                    'text': text,
                    'metadata': {
                        'source': f"sharepoint://{self.client.site_hostname}{self.client.site_path}/{file_name}",
                        'file_type': extension,
                        'size': file_item.get('size', 0),
                        'created_at': file_item.get('createdDateTime', ''),
                        'modified_at': file_item.get('lastModifiedDateTime', ''),
                        'url': file_item.get('webUrl', ''),
                        'sharepoint_id': file_id,
                        'mime_type': file_item.get('file', {}).get('mimeType', ''),
                        'graph_url': file_item.get('@microsoft.graph.downloadUrl', '')
                    }
                }
                documents.append(doc)
                logger.info(f"Processed: {file_name}")
            except Exception as e:
                logger.error(f"Error processing {file_item.get('name')}: {str(e)}")
                continue
        logger.info(f"Successfully processed {len(documents)} documents")
        return documents
