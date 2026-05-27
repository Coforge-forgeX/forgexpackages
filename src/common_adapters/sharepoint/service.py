import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
import concurrent.futures
logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class SharePointService:
    """Service layer for SharePoint document discovery, download and extraction."""

    def __init__(self, client):
        self.client = client

    # ---------------------- DOCUMENT INTELLIGENCE ----------------------
    def get_data_from_file(self, content: bytes) -> Optional[str]:
        """Extract text from raw file bytes using Azure Document Intelligence.

        Requires env vars AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and
        AZURE_DOCUMENT_INTELLIGENCE_KEY. Returns None on any failure.
        """
        endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        api_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        if not endpoint or not api_key:
            logger.error("Azure Document Intelligence endpoint or key not set in environment variables.")
            return None
        try:
            doc_client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(api_key))
            poller = doc_client.begin_analyze_document(
                "prebuilt-read",
                body=AnalyzeDocumentRequest(bytes_source=content),
                locale="en-US",
            )
            result = poller.result()
            return result.content
        except Exception as e:
            logger.error(f"Failed to process file with Document Intelligence: {e}")
            return None

    # ---------------------- GRAPH HELPERS ----------------------
    def _ensure_site(self) -> bool:
        if not self.client.site_id:
            self.client.get_site_id()
        return bool(self.client.site_id)

    @staticmethod
    def _strip_library_prefix(folder_path: str) -> str:
        """Graph drive/root already maps to 'Shared Documents'.
        Strip that prefix so callers can pass the full SharePoint path without 404."""
        stripped = folder_path.strip("/")
        for prefix in ("Shared Documents", "Shared%20Documents"):
            if stripped.lower() == prefix.lower():
                return ""
            if stripped.lower().startswith(prefix.lower() + "/"):
                return stripped[len(prefix) + 1:]
        return stripped

    def _children_url(self, folder_path: str) -> str:
        site_id = self.client.site_id
        cleaned = self._strip_library_prefix(folder_path)
        if not cleaned:
            return f"{GRAPH_BASE}/sites/{site_id}/drive/root/children?$expand=listItem($expand=fields)"
        normalized = f"/{cleaned}"
        return f"{GRAPH_BASE}/sites/{site_id}/drive/root:{normalized}:/children?$expand=listItem($expand=fields)"

    def _get_all_files_recursive(self, folder_path: str = "") -> List[Dict]:
        """Walk a folder tree and return every file item, following Graph pagination."""
        all_files: List[Dict] = []
        if not self._ensure_site():
            return all_files

        # Normalise once at entry so sub-paths are already clean
        clean_path = self._strip_library_prefix(folder_path)
        url: Optional[str] = self._children_url(clean_path)
        try:
            while url:
                response = requests.get(url, headers=self.client.get_headers())
                response.raise_for_status()
                payload = response.json()
                for item in payload.get("value", []):
                    if "folder" in item:
                        sub = f"{clean_path}/{item['name']}" if clean_path else item["name"]
                        all_files.extend(self._get_all_files_recursive(sub))
                    elif "file" in item:
                        all_files.append(item)
                url = payload.get("@odata.nextLink")
        except Exception as e:
            logger.error(f"Error listing folder contents for '{folder_path}': {e}")
        return all_files

    def list_files(self, folder_path: str = "") -> List[Dict]:
        return self._get_all_files_recursive(folder_path)

    def download_file(self, file_id: str) -> Optional[bytes]:
        if not self._ensure_site():
            return None
        try:
            file_url = f"{GRAPH_BASE}/sites/{self.client.site_id}/drive/items/{file_id}"
            response = requests.get(file_url, headers=self.client.get_headers())
            response.raise_for_status()
            download_url = response.json().get("@microsoft.graph.downloadUrl")
            if not download_url:
                logger.error(f"No download URL for file ID: {file_id}")
                return None
            blob = requests.get(download_url)
            blob.raise_for_status()
            logger.info(f"Downloaded file ID {file_id} ({len(blob.content)} bytes)")
            return blob.content
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return None

    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        if not self._ensure_site():
            return None
        try:
            file_url = f"{GRAPH_BASE}/sites/{self.client.site_id}/drive/items/{file_id}"
            response = requests.get(file_url, headers=self.client.get_headers())
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting file metadata: {e}")
            return None

    # ---------------------- METADATA FILTER ----------------------
    @staticmethod
    def _normalize_field_value(val) -> set:
        """Return a flat set of lowercase strings from any SharePoint field value."""
        def _norm(v):
            if isinstance(v, (int, float)):
                return str(v)
            return str(v).strip().lower()

        if isinstance(val, list):
            result = set()
            for item in val:
                if isinstance(item, dict):
                    label = (
                        item.get("Label") or item.get("label") or
                        item.get("name") or item.get("Name") or
                        item.get("Value") or item.get("value") or
                        item.get("LookupValue") or str(item)
                    )
                    result.add(_norm(label))
                else:
                    result.add(_norm(item))
            return result

        s = str(val).strip()
        if ";" in s:
            parts = [p.lstrip("#").strip() for p in s.split(";") if p.strip().lstrip("#")]
            return {p.lower() for p in parts if p}

        return {_norm(val)}

    @staticmethod
    def _normalize_extension(ext: str) -> str:
        ext = ext.lower().strip()
        return ext if ext.startswith(".") else f".{ext}"

    @staticmethod
    def _parse_date(value: Union[str, datetime, None]) -> Optional[datetime]:
        """
        Parse a date string or datetime object and ensure it is timezone-aware (UTC).
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except Exception:
                logger.warning(f"Could not parse date value: {value}")
                return None
        # Make timezone-aware if naive
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _should_process_file(self, file_item: Dict, metadata_map: Optional[Dict]) -> bool:
        """Return True if the file passes all configured metadata filters.

        Supported keys in metadata_map:
          - file_types: list[str]          (extensions, with or without leading dot)
          - name_contains: str             (case-insensitive substring)
          - min_size / max_size: int       (bytes)
          - created_after / created_before: datetime | iso str
          - modified_after / modified_before: datetime | iso str
          - tags: dict[str, Any]           (SharePoint column key → expected value; all must match)
        """
        if not metadata_map:
            return True

        file_name = file_item.get("name", "")
        file_size = file_item.get("size", 0)
        extension = Path(file_name).suffix.lower()
        created = file_item.get("createdDateTime")
        modified = file_item.get("lastModifiedDateTime")

        file_types = metadata_map.get("file_types")
        if file_types:
            allowed = {self._normalize_extension(e) for e in file_types}
            if extension not in allowed:
                return False

        name_contains = metadata_map.get("name_contains")
        if name_contains and name_contains.lower() not in file_name.lower():
            return False

        min_size = metadata_map.get("min_size")
        if min_size is not None and file_size < min_size:
            return False

        max_size = metadata_map.get("max_size")
        if max_size is not None and file_size > max_size:
            return False

        if created:
            created_dt = self._parse_date(created)
            if created_dt:
                after = self._parse_date(metadata_map.get("created_after"))
                before = self._parse_date(metadata_map.get("created_before"))
                if after and created_dt < after:
                    return False
                if before and created_dt > before:
                    return False

        if modified:
            modified_dt = self._parse_date(modified)
            if modified_dt:
                after = self._parse_date(metadata_map.get("modified_after"))
                before = self._parse_date(metadata_map.get("modified_before"))
                if after and modified_dt < after:
                    return False
                if before and modified_dt > before:
                    return False

        tags_filter = metadata_map.get("tags")
        if tags_filter:
            fields = (file_item.get("listItem") or {}).get("fields") or {}
            fields_lower = {k.lower(): v for k, v in fields.items()}

            def norm(val):
                if isinstance(val, (int, float)):
                    return str(val)
                return str(val).strip().lower()

            for col_key, expected in tags_filter.items():
                actual = fields_lower.get(col_key.lower())
                if actual is None:
                    return False

                actual_vals = self._normalize_field_value(actual)

                if isinstance(expected, list):
                    matched = any(norm(e) in actual_vals for e in expected)
                    if not matched:
                        return False
                else:
                    matched = norm(expected) in actual_vals
                    if not matched:
                        return False

        return True

    # ---------------------- EXTRACTION ----------------------
    def extract_data(
        self,
        folder_path: str = "",
        metadata_map: Optional[Dict] = None,
        max_workers: int = 5,
    ) -> List[Dict]:
        """List files under folder_path, apply metadata filter, download, and OCR each match (parallelized)."""
       

        if not self._ensure_site():
            logger.error("SharePoint site not ensured. Aborting extract_data.")
            return []

        documents: List[Dict] = []
        files = self._get_all_files_recursive(folder_path)
        logger.info(f"Found {len(files)} files under '{folder_path or '/'}'")

        def process_file(file_item):
            file_id = file_item.get("id")
            file_name = file_item.get("name")
            try:
                if metadata_map and not self._should_process_file(file_item, metadata_map):
                    logger.info(f"Skipped (metadata filter): {file_name}")
                    return None

                logger.debug(f"Attempting to download file: {file_name} (id={file_id})")
                content = self.download_file(file_id)
                if not content:
                    logger.warning(f"Could not download {file_name}")
                    return None

                extension = Path(file_name).suffix.lower()
                text = self.get_data_from_file(content)

                sp_fields = (file_item.get("listItem") or {}).get("fields") or {}
                doc = {
                    "id": file_id,
                    "name": file_name,
                    "content": text,
                    "metadata": {
                        "source": f"sharepoint://{self.client.site_hostname}{self.client.site_path}/{file_name}",
                        "file_type": extension,
                        "size": file_item.get("size", 0),
                        "created_at": file_item.get("createdDateTime", ""),
                        "modified_at": file_item.get("lastModifiedDateTime", ""),
                        "url": file_item.get("webUrl", ""),
                        "sharepoint_id": file_id,
                        "mime_type": file_item.get("file", {}).get("mimeType", ""),
                        "tags": sp_fields,
                    },
                }
                logger.info(f"Processed: {file_name}")
                return doc
            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}", exc_info=True)
                return None

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(process_file, files))
            documents = [doc for doc in results if doc is not None]
        except Exception as e:
            logger.error(f"Unexpected error in extract_data: {e}", exc_info=True)

        logger.info(f"Successfully processed {len(documents)} documents out of {len(files)} files")
        return documents
