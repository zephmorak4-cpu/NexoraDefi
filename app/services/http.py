import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class ExternalAPIError(RuntimeError):
    pass


class AsyncAPIClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
        headers: Mapping[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.max_retries = max_retries
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers=dict(headers or {})
        )

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(
                    method, path, params=params, data=data, headers=headers
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt >= self.max_retries:
                        response.raise_for_status()
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else min(2**attempt, 8)
                    logger.warning(
                        "external_api_retry",
                        path=path,
                        status=response.status_code,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = min(2**attempt, 8)
                logger.warning(
                    "external_api_error_retry",
                    path=path,
                    error=type(exc).__name__,
                    attempt=attempt + 1,
                    delay=delay,
                )
                await asyncio.sleep(delay)
            except (ValueError, TypeError) as exc:
                raise ExternalAPIError(f"invalid JSON response from {path}") from exc
        raise ExternalAPIError(f"request failed after retries: {method} {path}") from last_error

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

