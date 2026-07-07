from __future__ import annotations

from typing import Any

import httpx

from app.alpha_discovery.types import ProviderSnapshot
from app.alpha_discovery.utils import number
from app.core.config import Settings


class SolanaRPCService:
    provider = "SOLANA_RPC"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.enabled = settings.solana_rpc_enabled
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(base_url=settings.solana_rpc_url, timeout=settings.provider_timeout_ms / 1000)

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        response = await self.client.post("/", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        response.raise_for_status()
        payload = response.json()
        return payload.get("result") if isinstance(payload, dict) else None

    async def get_token_supply(self, token_address: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return await self._rpc("getTokenSupply", [token_address])

    async def get_mint_info(self, token_address: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return await self._rpc("getAccountInfo", [token_address, {"encoding": "jsonParsed"}])

    async def get_account_info(self, address: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return await self._rpc("getAccountInfo", [address, {"encoding": "jsonParsed"}])

    async def get_token_largest_accounts(self, token_address: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return await self._rpc("getTokenLargestAccounts", [token_address])

    async def enrich(self, token_address: str) -> dict[str, Any]:
        supply = await self.get_token_supply(token_address)
        mint = await self.get_mint_info(token_address)
        largest = await self.get_token_largest_accounts(token_address)
        supply_amount = number(((supply or {}).get("value") or {}).get("uiAmount"))
        accounts = (largest or {}).get("value") if isinstance(largest, dict) else []
        top10_amount = sum(number(item.get("uiAmount")) or 0 for item in accounts[:10] if isinstance(item, dict))
        parsed = (((mint or {}).get("value") or {}).get("data") or {}).get("parsed") or {}
        info = parsed.get("info") or {}
        mint_authority = info.get("mintAuthority")
        freeze_authority = info.get("freezeAuthority")
        normalized = {
            "top10_holder_percent": (top10_amount / supply_amount * 100) if supply_amount else None,
            "mint_authority": mint_authority,
            "freeze_authority": freeze_authority,
            "mint_authority_active": bool(mint_authority),
            "freeze_authority_active": bool(freeze_authority),
            "risk_flags": [],
            "_source": "Solana RPC",
        }
        normalized["_snapshot"] = ProviderSnapshot(self.provider, {"supply": supply, "mint": mint, "largest_accounts": largest}, normalized.copy())
        return normalized

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()
