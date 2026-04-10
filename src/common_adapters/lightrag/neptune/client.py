import os, json, aiohttp, asyncio
from typing import Any, Dict

class NeptuneGatewayClient:
    def __init__(self, base_url: str, timeout: int = 0, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self.api_key  = api_key

    async def call(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        print(self.base_url)
        url = f"{self.base_url}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        body = {"action": action, **payload}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as sess:
            async with sess.post(url, data=json.dumps(body), headers=headers) as resp:
                txt = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"Neptune gateway {resp.status}: {txt}")
                return json.loads(txt)