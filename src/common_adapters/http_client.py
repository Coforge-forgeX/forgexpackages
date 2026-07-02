"""
Shared HTTP Client Utility

Async HTTP client with retry logic, exponential backoff, and connection pooling.
Uses httpx.AsyncClient for true async/await concurrency without thread pool overhead.
"""

import httpx
import asyncio
import time
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HTTPClient:
    """
    Async HTTP client with retry logic, exponential backoff, and connection pooling.
    Uses httpx.AsyncClient for true async/await concurrency without thread pool overhead.
    """

    def __init__(self, base_url: str = "", timeout: int = 30, default_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip('/')
        self.timeout = httpx.Timeout(timeout)
        self.default_headers = default_headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of async client (singleton pattern)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.default_headers,
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            )
        return self._client

    def _should_retry(self, status_code: int, attempt: int, max_retries: int) -> bool:
        """Determine if we should retry the request based on status code and attempt count."""
        if attempt >= max_retries:
            return False
        # Retry on rate limiting (429) or server errors (5xx)
        if status_code in [429, 500, 502, 503, 504]:
            return True
        return False

    def _calculate_backoff(self, attempt: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay."""
        return base_delay * (2 ** attempt)

    def _handle_rate_limit(self, headers: Dict[str, str]) -> float:
        """Handle rate limiting by checking reset time."""
        reset_time = headers.get('x-ratelimit-reset')
        if reset_time:
            try:
                reset_timestamp = int(reset_time)
                current_time = time.time()
                wait_time = max(0, reset_timestamp - current_time)
                return min(wait_time, 3600)  # Cap at 1 hour
            except (ValueError, TypeError):
                pass
        return 60  # Default 1 minute wait

    async def _make_request_async(self, method: str, url: str, params: Optional[Dict[str, Any]] = None,
                                  data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None,
                                  headers: Optional[Dict[str, str]] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Make an async HTTP request with retry logic."""
        client = await self._get_client()
        request_headers = dict(self.default_headers)
        if headers:
            request_headers.update(headers)

        for attempt in range(max_retries + 1):
            try:
                response = await client.request(
                    method.upper(),
                    url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=request_headers
                )

                if response.status_code == 200:
                    return {
                        'status_code': response.status_code,
                        'data': response.json() if response.content else None,
                        'headers': dict(response.headers)
                    }
                elif response.status_code == 404:
                    return {
                        'status_code': response.status_code,
                        'error': 'Resource not found',
                        'data': None
                    }
                elif response.status_code == 403:
                    if 'rate limit' in response.text.lower():
                        wait_time = self._handle_rate_limit(dict(response.headers))
                        logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry.")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return {
                            'status_code': response.status_code,
                            'error': 'Forbidden - insufficient permissions',
                            'data': None
                        }
                elif response.status_code == 401:
                    return {
                        'status_code': response.status_code,
                        'error': 'Unauthorized - invalid credentials',
                        'data': None
                    }
                elif self._should_retry(response.status_code, attempt, max_retries):
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(f"Request failed with {response.status_code}. Retrying in {backoff}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(backoff)
                    continue
                else:
                    return {
                        'status_code': response.status_code,
                        'error': f'Request failed with status {response.status_code}',
                        'data': response.json() if response.content else None
                    }

            except httpx.TimeoutException:
                if attempt < max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(f"Request timed out. Retrying in {backoff}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(backoff)
                    continue
                return {'status_code': 408, 'error': 'Request timed out', 'data': None}

            except httpx.RequestError as e:
                if attempt < max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(f"Request error: {e}. Retrying in {backoff}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(backoff)
                    continue
                return {'status_code': 0, 'error': str(e), 'data': None}

        return {'status_code': 0, 'error': 'Max retries exceeded', 'data': None}

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Make an async GET request."""
        return await self._make_request_async('GET', url, params=params, headers=headers, max_retries=max_retries)

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None,
                   json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                   max_retries: int = 3) -> Dict[str, Any]:
        """Make an async POST request."""
        return await self._make_request_async('POST', url, data=data, json_data=json_data, headers=headers, max_retries=max_retries)

    async def put(self, url: str, data: Optional[Dict[str, Any]] = None,
                  json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                  max_retries: int = 3) -> Dict[str, Any]:
        """Make an async PUT request."""
        return await self._make_request_async('PUT', url, data=data, json_data=json_data, headers=headers, max_retries=max_retries)

    async def delete(self, url: str, headers: Optional[Dict[str, str]] = None,
                     max_retries: int = 3) -> Dict[str, Any]:
        """Make an async DELETE request."""
        return await self._make_request_async('DELETE', url, headers=headers, max_retries=max_retries)

    async def patch(self, url: str, data: Optional[Dict[str, Any]] = None,
                    json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                    max_retries: int = 3) -> Dict[str, Any]:
        """Make an async PATCH request."""
        return await self._make_request_async('PATCH', url, data=data, json_data=json_data, headers=headers, max_retries=max_retries)

    async def close(self):
        """Close the HTTP client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
