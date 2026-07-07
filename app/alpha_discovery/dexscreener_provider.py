from __future__ import annotations

from typing import Any

from app.alpha_discovery.normalize import normalize_dex_pair
from app.alpha_discovery.types import ProviderSnapshot, TokenLaunch
from app.core.config import Settings
from app.services.http import AsyncAPIClient


class DexScreenerService:
    provider = "DEXSCREENER"

    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.provider_timeout_ms / 1000,
            max_retries=settings.provider_retry_count,
        )

    async def get_latest_solana_pairs(self) -> list[TokenLaunch]:
        payload = await self.client.request_json("GET", "/token-profiles/latest/v1")
        profiles = payload if isinstance(payload, list) else []
        launches: list[TokenLaunch] = []
        for profile in profiles:
            if not isinstance(profile, dict) or profile.get("chainId") != "solana":
                continue
            token = str(profile.get("tokenAddress") or "")
            if not token:
                continue
            launches.extend(await self.get_token_pairs(token, profile))
            if len(launches) >= self.settings.alpha_launch_scan_limit:
                break
        return launches[: self.settings.alpha_launch_scan_limit]

    async def get_token_pairs(self, token_address: str, profile: dict[str, Any] | None = None) -> list[TokenLaunch]:
        try:
            payload = await self.client.request_json("GET", f"/token-pairs/v1/solana/{token_address}")
        except Exception:
            normalized = {"tokenAddress": token_address, "source": "DEXSCREENER", "pairAddress": None}
            return [
                TokenLaunch(
                    token_address=token_address,
                    source="DEXSCREENER",
                    dex="unknown",
                    sources=["DEX Screener"],
                    provider_snapshots=[ProviderSnapshot(self.provider, profile, normalized)],
                )
            ]
        pairs = payload if isinstance(payload, list) else []
        launches = [
            normalize_dex_pair(pair, profile)
            for pair in pairs
            if isinstance(pair, dict) and (not pair.get("chainId") or pair.get("chainId") == "solana")
        ]
        if launches:
            return launches
        normalized = {"tokenAddress": token_address, "source": "DEXSCREENER", "pairAddress": None}
        return [
            TokenLaunch(
                token_address=token_address,
                source="DEXSCREENER",
                dex="unknown",
                sources=["DEX Screener"],
                provider_snapshots=[ProviderSnapshot(self.provider, profile, normalized)],
            )
        ]

    async def get_pair_details(self, pair_address: str) -> dict[str, Any] | None:
        payload = await self.client.request_json("GET", f"/latest/dex/pairs/solana/{pair_address}")
        pairs = payload.get("pairs") if isinstance(payload, dict) else None
        if isinstance(pairs, list) and pairs:
            return pairs[0]
        return None

    async def close(self) -> None:
        await self.client.close()
