from __future__ import annotations

from typing import Any

from app.alpha_discovery.types import TokenLaunch, TokenTxns
from app.alpha_discovery.utils import number
from app.core.config import Settings
from app.core.logging import get_logger
from app.services.http import AsyncAPIClient
from app.telegram.client import TelegramClient

logger = get_logger(__name__)


class MarketDataService:
    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )

    async def latest_solana_launches(self) -> list[TokenLaunch]:
        payload = await self.client.request_json("GET", "/token-profiles/latest/v1")
        profiles = payload if isinstance(payload, list) else []
        launches: list[TokenLaunch] = []
        for profile in profiles:
            if not isinstance(profile, dict) or profile.get("chainId") != "solana":
                continue
            token = str(profile.get("tokenAddress") or "")
            if not token:
                continue
            launches.extend(await self._pairs_for_token(token, profile))
            if len(launches) >= self.settings.alpha_launch_scan_limit:
                break
        logger.info("alpha_market_data_launches_loaded", count=len(launches))
        return launches[: self.settings.alpha_launch_scan_limit]

    async def _pairs_for_token(self, token: str, profile: dict[str, Any]) -> list[TokenLaunch]:
        try:
            payload = await self.client.request_json("GET", f"/token-pairs/v1/solana/{token}")
        except Exception as exc:
            logger.warning("alpha_pair_lookup_failed", token=token, error=type(exc).__name__)
            return [self._from_profile(profile)]
        pairs = payload if isinstance(payload, list) else []
        launches = [self._from_pair(pair, profile) for pair in pairs if isinstance(pair, dict)]
        return launches or [self._from_profile(profile)]

    @staticmethod
    def _from_profile(profile: dict[str, Any]) -> TokenLaunch:
        return TokenLaunch(
            token_address=str(profile.get("tokenAddress") or ""),
            source="dexscreener-profile",
            dex="unknown",
        )

    @staticmethod
    def _from_pair(pair: dict[str, Any], profile: dict[str, Any]) -> TokenLaunch:
        base = pair.get("baseToken") or {}
        liquidity = pair.get("liquidity") or {}
        volume = pair.get("volume") or {}
        txns = pair.get("txns") or {}
        h24 = txns.get("h24") or {}
        return TokenLaunch(
            token_address=str(base.get("address") or profile.get("tokenAddress") or ""),
            pair_address=pair.get("pairAddress"),
            symbol=base.get("symbol"),
            name=base.get("name"),
            launch_time=str(pair.get("pairCreatedAt")) if pair.get("pairCreatedAt") else None,
            dex=pair.get("dexId"),
            source="dexscreener",
            liquidity_usd=number(liquidity.get("usd")),
            market_cap_usd=number(pair.get("marketCap") or pair.get("fdv")),
            price_usd=number(pair.get("priceUsd")),
            volume_usd=number(volume.get("h24")),
            txns=TokenTxns(buys=int(h24.get("buys") or 0), sells=int(h24.get("sells") or 0)),
        )

    async def close(self) -> None:
        await self.client.close()


class TelegramAlphaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = TelegramClient(settings.telegram_bot_token or "") if settings.telegram_bot_token else None

    async def send(self, message: str) -> bool:
        if not self.settings.telegram_alerts_enabled:
            logger.info("alpha_telegram_skipped", reason="disabled")
            return False
        if not self.client or not self.settings.telegram_chat_id:
            logger.info("alpha_telegram_skipped", reason="missing_token_or_chat_id")
            return False
        await self.client.send_message(self.settings.telegram_chat_id, message)
        return True

    async def close(self) -> None:
        if self.client:
            await self.client.close()


class DiscordAlphaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: str) -> bool:
        if self.settings.discord_alerts_enabled:
            logger.info("alpha_discord_placeholder", configured=bool(self.settings.discord_webhook_url))
        return False


class OpenAIAlphaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def summarize(self, reasons: list[str]) -> str:
        return " ".join(reasons[:4])
