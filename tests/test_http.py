import httpx

from app.services.http import AsyncAPIClient


async def test_api_client_retries_rate_limit():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    http_client = httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler))
    client = AsyncAPIClient("https://example.test", max_retries=1, client=http_client)
    assert await client.request_json("GET", "/data") == {"ok": True}
    assert attempts == 2
    await http_client.aclose()

