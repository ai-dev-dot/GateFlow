import httpx
from typing import Optional

_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    return _client


async def close_http_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
