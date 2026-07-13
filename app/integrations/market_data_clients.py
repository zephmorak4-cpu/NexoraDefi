from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.services.http import AsyncAPIClient


class DexScreenerClient:
    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
        )

    async def request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.client.request_json("GET", path, params=params)

    async def health_check(self) -> str:
        if not self.settings.dexscreener_enabled:
            return "DISABLED"
        try:
            await self.request("/token-profiles/latest/v1")
            return "AVAILABLE"
        except Exception:
            return "UNAVAILABLE"

    async def close(self) -> None:
        await self.client.close()


class BirdeyeClient:
    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        headers = {"X-API-KEY": settings.birdeye_api_key or "", "x-chain": "solana"}
        self.client = client or AsyncAPIClient(
            "https://public-api.birdeye.so",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
            headers=headers,
        )

    async def request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.client.request_json("GET", path, params=params)

    def configuration_status(self) -> str:
        if not self.settings.birdeye_enabled:
            return "DISABLED"
        return "CONFIGURED" if self.settings.birdeye_api_key else "NOT_CONFIGURED"

    async def close(self) -> None:
        await self.client.close()


class HeliusClient:
    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAPIClient(
            "https://api.helius.xyz",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
        )

    async def request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        if self.settings.helius_api_key:
            params.setdefault("api-key", self.settings.helius_api_key)
        return await self.client.request_json("GET", path, params=params)

    def configuration_status(self) -> str:
        if not self.settings.helius_enabled:
            return "DISABLED"
        return "CONFIGURED" if self.settings.helius_api_key else "NOT_CONFIGURED"

    async def close(self) -> None:
        await self.client.close()


class SolanaRPCClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            base_url=settings.solana_rpc_url,
            timeout=settings.provider_timeout_ms / 1000,
        )
        self._owns_client = client is None

    async def request(self, method: str, params: list[Any] | None = None) -> Any:
        response = await self.client.post(
            "",
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
        )
        response.raise_for_status()
        return response.json()

    def configuration_status(self) -> str:
        if not self.settings.solana_rpc_enabled:
            return "DISABLED"
        return "CONFIGURED" if self.settings.solana_rpc_url else "NOT_CONFIGURED"

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()


class GeckoTerminalClient:
    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAPIClient(
            "https://api.geckoterminal.com/api/v2",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
        )

    async def request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.client.request_json("GET", path, params=params)

    async def network_pools(self, page: int = 1) -> Any:
        return await self.request("/networks/solana/pools", params={"page": page})

    async def ohlcv(self, pool_address: str, timeframe: str, aggregate: int = 1, limit: int = 200) -> Any:
        path = f"/networks/solana/pools/{pool_address}/ohlcv/{timeframe}"
        return await self.request(path, params={"aggregate": aggregate, "limit": limit})

    def configuration_status(self) -> str:
        return "CONFIGURED" if self.settings.geckoterminal_enabled else "DISABLED"

    async def close(self) -> None:
        await self.client.close()


class JupiterClient:
    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAPIClient(
            "https://quote-api.jup.ag",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
        )

    async def quote(self, input_mint: str, output_mint: str, amount: int) -> Any:
        return await self.client.request_json(
            "GET",
            "/v6/quote",
            params={"inputMint": input_mint, "outputMint": output_mint, "amount": amount},
        )

    def configuration_status(self) -> str:
        return "CONFIGURED" if self.settings.jupiter_enabled else "DISABLED"

    async def close(self) -> None:
        await self.client.close()
