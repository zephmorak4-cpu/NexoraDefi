from __future__ import annotations

from typing import Any

from app.alpha_discovery.types import ProviderSnapshot
from app.core.config import Settings
from app.core.logging import get_logger
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)


class HeliusService:
    provider = "HELIUS"

    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.enabled = settings.helius_enabled and bool(settings.helius_api_key)
        self.client = client or AsyncAPIClient(
            "https://api.helius.xyz",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
        )

    async def get_token_transactions(self, token_address: str) -> list[dict[str, Any]]:
        if not self.enabled:
            logger.warning("alpha_helius_skipped", reason="missing_api_key")
            return []
        payload = await self.client.request_json(
            "GET",
            f"/v0/addresses/{token_address}/transactions",
            params={"api-key": self.settings.helius_api_key or "", "limit": 50},
        )
        return payload if isinstance(payload, list) else []

    async def get_wallet_transactions(self, wallet_address: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        payload = await self.client.request_json(
            "GET",
            f"/v0/addresses/{wallet_address}/transactions",
            params={"api-key": self.settings.helius_api_key or "", "limit": 50},
        )
        return payload if isinstance(payload, list) else []

    async def get_token_holders_if_available(self, token_address: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        payload = await self.client.request_json(
            "POST",
            "/v0/token-metadata",
            params={"api-key": self.settings.helius_api_key or ""},
            data={"mintAccounts": [token_address]},
        )
        return {"metadata": payload} if payload else None

    async def enrich(self, token_address: str) -> dict[str, Any]:
        transactions = await self.get_token_transactions(token_address)
        buys = 0
        sells = 0
        for item in transactions:
            kind = str(item.get("type") or item.get("transactionType") or "").lower()
            if "swap" in kind or "buy" in kind:
                buys += 1
            elif "sell" in kind:
                sells += 1
        normalized = {
            "txns_1h": None,
            "risk_flags": [],
            "_source": "Helius",
        }
        if buys or sells:
            normalized["txns_1h"] = {"buys": buys, "sells": sells}
        normalized["_snapshot"] = ProviderSnapshot(self.provider, {"transactions": transactions[:10]}, normalized.copy())
        return normalized

    async def close(self) -> None:
        await self.client.close()
