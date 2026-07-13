from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.alpha_discovery.birdeye_provider import BirdeyeService
from app.alpha_discovery.dexscreener_provider import DexScreenerService
from app.alpha_discovery.helius_provider import HeliusService
from app.alpha_discovery.normalize import merge_token_data
from app.alpha_discovery.provider_health import ProviderHealthService
from app.alpha_discovery.solana_rpc_provider import SolanaRPCService
from app.alpha_discovery.types import TokenLaunch
from app.alpha_discovery.utils import safe_provider_call
from app.core.config import Settings
from app.core.logging import get_logger
from app.services.http import AsyncAPIClient
from app.telegram.client import TelegramClient

logger = get_logger(__name__)


class MarketDataService:
    def __init__(
        self,
        settings: Settings,
        client: AsyncAPIClient | None = None,
        dexscreener: DexScreenerService | None = None,
        birdeye: BirdeyeService | None = None,
        helius: HeliusService | None = None,
        solana_rpc: SolanaRPCService | None = None,
        health: ProviderHealthService | None = None,
    ) -> None:
        self.settings = settings
        self.dexscreener = dexscreener or DexScreenerService(settings, client=client)
        self.birdeye = birdeye or BirdeyeService(settings)
        self.helius = helius or HeliusService(settings)
        self.solana_rpc = solana_rpc or SolanaRPCService(settings)
        self.health = health or ProviderHealthService()
        self.last_launch_diagnostics: dict[str, Any] = {}

    async def latest_solana_launches(self) -> list[TokenLaunch]:
        return await self.get_new_solana_launches()

    async def get_new_solana_launches(self) -> list[TokenLaunch]:
        result = await safe_provider_call("DEXSCREENER", self.dexscreener.get_latest_solana_pairs)
        if not result.ok:
            self.health.failure(result.provider, result.error)
            self.last_launch_diagnostics = {
                "provider": result.provider,
                "status": "failed",
                "error": result.error,
                "raw_candidates": 0,
                "within_lookback": 0,
                "deduped": 0,
                "enriched": 0,
            }
            logger.warning("[LaunchDetector] Provider: DEXSCREENER unavailable")
            return []
        self.health.success(result.provider)
        raw_launches = result.data or []
        launches = [token for token in raw_launches if self._within_lookback(token)]
        logger.info("[LaunchDetector] Provider: DEXSCREENER")
        logger.info("[LaunchDetector] New Solana launches found: %s", len(launches))
        deduped = self._dedupe(launches)
        logger.info("[LaunchDetector] After dedupe: %s", len(deduped))
        enriched: list[TokenLaunch] = []
        for token in deduped[: self.settings.alpha_launch_scan_limit]:
            enriched.append(await self.get_enriched_token_data(token))
        self.last_launch_diagnostics = {
            "provider": result.provider,
            "status": "ok",
            "error": None,
            "raw_candidates": len(raw_launches),
            "within_lookback": len(launches),
            "deduped": len(deduped),
            "enriched": len(enriched),
        }
        logger.info("alpha_market_data_launches_loaded", count=len(enriched), provider_health=self.health.snapshot())
        return enriched

    async def get_enriched_token_data(self, token: TokenLaunch | str) -> TokenLaunch:
        launch = token if isinstance(token, TokenLaunch) else TokenLaunch(token_address=token)
        updates: list[dict[str, Any]] = []
        if self.settings.birdeye_enabled:
            result = await safe_provider_call("BIRDEYE", lambda: self.birdeye.enrich(launch.token_address))
            if result.ok and result.data:
                self.health.success(result.provider)
                updates.append(result.data)
            else:
                self.health.failure(result.provider, result.error or "unavailable")
        if self.settings.helius_enabled:
            result = await safe_provider_call("HELIUS", lambda: self.helius.enrich(launch.token_address))
            if result.ok and result.data:
                self.health.success(result.provider)
                updates.append(result.data)
            else:
                self.health.failure(result.provider, result.error or "unavailable")
        if self.settings.solana_rpc_enabled:
            result = await safe_provider_call("SOLANA_RPC", lambda: self.solana_rpc.enrich(launch.token_address))
            if result.ok and result.data:
                self.health.success(result.provider)
                updates.append(result.data)
            else:
                self.health.failure(result.provider, result.error or "unavailable")
        return merge_token_data(launch, *updates)

    async def get_token_risk_data(self, token_address: str) -> TokenLaunch:
        return await self.get_enriched_token_data(token_address)

    async def get_token_momentum_data(self, token_address: str) -> TokenLaunch:
        return await self.get_enriched_token_data(token_address)

    def _within_lookback(self, token: TokenLaunch) -> bool:
        if not token.launch_time:
            return True
        try:
            timestamp = datetime.fromtimestamp(int(token.launch_time) / 1000, tz=timezone.utc)
        except (TypeError, ValueError):
            return True
        return timestamp >= datetime.now(timezone.utc) - timedelta(minutes=self.settings.new_pair_lookback_minutes)

    @staticmethod
    def _dedupe(tokens: list[TokenLaunch]) -> list[TokenLaunch]:
        seen: set[str] = set()
        deduped: list[TokenLaunch] = []
        for token in tokens:
            if token.token_address in seen:
                continue
            seen.add(token.token_address)
            deduped.append(token)
        return deduped

    async def close(self) -> None:
        await self.dexscreener.close()
        await self.birdeye.close()
        await self.helius.close()
        await self.solana_rpc.close()


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

    async def send_document(self, document_path: str, caption: str) -> bool:
        if not self.settings.telegram_alerts_enabled:
            logger.info("alpha_telegram_document_skipped", reason="disabled")
            return False
        if not self.client or not self.settings.telegram_chat_id:
            logger.info("alpha_telegram_document_skipped", reason="missing_token_or_chat_id")
            return False
        await self.client.send_document(self.settings.telegram_chat_id, document_path, caption=caption)
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
