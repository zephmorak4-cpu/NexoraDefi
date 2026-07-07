from __future__ import annotations

from typing import Any

from app.alpha_discovery.types import ProviderSnapshot
from app.alpha_discovery.utils import number
from app.core.config import Settings
from app.core.logging import get_logger
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)


class BirdeyeService:
    provider = "BIRDEYE"

    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.enabled = settings.birdeye_enabled and bool(settings.birdeye_api_key)
        headers = {"X-API-KEY": settings.birdeye_api_key or "", "x-chain": "solana"}
        self.client = client or AsyncAPIClient(
            "https://public-api.birdeye.so",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
            headers=headers,
        )

    async def get_token_overview(self, token_address: str) -> dict[str, Any] | None:
        if not self.enabled:
            logger.warning("alpha_birdeye_skipped", reason="missing_api_key")
            return None
        payload = await self.client.request_json("GET", "/defi/token_overview", params={"address": token_address})
        return payload.get("data") if isinstance(payload, dict) else None

    async def get_holder_distribution(self, token_address: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        payload = await self.client.request_json("GET", "/defi/v3/token/holder", params={"address": token_address, "offset": 0, "limit": 10})
        return payload.get("data") if isinstance(payload, dict) else None

    async def get_token_security(self, token_address: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        payload = await self.client.request_json("GET", "/defi/token_security", params={"address": token_address})
        return payload.get("data") if isinstance(payload, dict) else None

    async def enrich(self, token_address: str) -> dict[str, Any]:
        overview = await self.get_token_overview(token_address)
        holders = await self.get_holder_distribution(token_address)
        security = await self.get_token_security(token_address)
        holder_items = []
        if isinstance(holders, dict):
            holder_items = holders.get("items") or holders.get("holders") or []
        top10 = sum(number(item.get("percentage") or item.get("percent")) or 0 for item in holder_items[:10] if isinstance(item, dict))
        normalized = {
            "holder_count": int(number((overview or {}).get("holder") or (overview or {}).get("holderCount")) or 0) or None,
            "top10_holder_percent": top10 or number((security or {}).get("top10HolderPercent")),
            "creator_hold_percent": number((security or {}).get("creatorPercentage") or (security or {}).get("creatorHoldPercent")),
            "liquidity_usd": number((overview or {}).get("liquidity")),
            "market_cap_usd": number((overview or {}).get("mc") or (overview or {}).get("marketCap")),
            "volume_usd_24h": number((overview or {}).get("v24hUSD") or (overview or {}).get("volume24hUSD")),
            "volume_usd_1h": number((overview or {}).get("v1hUSD")),
            "volume_usd_5m": number((overview or {}).get("v5mUSD")),
            "mint_authority": (security or {}).get("mintAuthority"),
            "freeze_authority": (security or {}).get("freezeAuthority"),
            "is_mutable": (security or {}).get("mutableMetadata"),
            "risk_flags": [key for key, value in (security or {}).items() if isinstance(value, bool) and value],
        }
        normalized["_source"] = "Birdeye"
        normalized["_snapshot"] = ProviderSnapshot(self.provider, {"overview": overview, "holders": holders, "security": security}, normalized.copy())
        return normalized

    async def close(self) -> None:
        await self.client.close()
