from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.market_data_clients import DexScreenerClient, GeckoTerminalClient
from app.models import ProviderHealthRecord
from app.spot.types import ProviderStatus, ReadinessState


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    discovery: bool = False
    quotes: bool = False
    ohlcv: bool = False
    liquidity: bool = False
    volume: bool = False
    metadata: bool = False
    required: bool = False


@dataclass
class ProviderCheck:
    provider: str
    capability: str
    status: ProviderStatus
    latency_ms: int | None = None
    action: str = "none"
    error: str | None = None
    last_success_at: datetime | None = None


@dataclass
class CapabilityAudit:
    state: ReadinessState
    checks: list[ProviderCheck]
    matrix: list[ProviderCapability]
    missing_capabilities: list[str] = field(default_factory=list)


CAPABILITY_MATRIX = [
    ProviderCapability("DEX Screener", discovery=True, quotes=True, liquidity=True, volume=True, metadata=True, required=True),
    ProviderCapability("GeckoTerminal", discovery=True, quotes=True, ohlcv=True, liquidity=True, volume=True, metadata=True, required=True),
    ProviderCapability("Helius", metadata=True, required=False),
    ProviderCapability("Solana RPC", metadata=True, required=False),
    ProviderCapability("Jupiter", quotes=True, required=False),
    ProviderCapability("CoinGecko", discovery=True, quotes=True, ohlcv=True, volume=True, required=False),
]


class ProviderCapabilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def audit(self, session: AsyncSession | None = None, live: bool = True) -> CapabilityAudit:
        checks = [
            await self._check_dexscreener(live),
            await self._check_geckoterminal(live),
            self._configured("Telegram", "notifications", bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id), required=self.settings.telegram_signals_enabled),
            self._configured("Database", "persistence", True, required=True),
        ]
        if session:
            for check in checks:
                await self._persist(session, check)
            await session.commit()
        healthy = {check.provider: check for check in checks if check.status == ProviderStatus.HEALTHY}
        missing: list[str] = []
        if "DEX Screener" not in healthy and "GeckoTerminal" not in healthy:
            missing.append("token/pool discovery")
        if "GeckoTerminal" not in healthy:
            missing.append("15m/1h/4h OHLCV candles")
        if "DEX Screener" not in healthy and "GeckoTerminal" not in healthy:
            missing.append("current price quotes")
        if self.settings.telegram_signals_enabled and "Telegram" not in healthy:
            missing.append("Telegram notifications")
        state = ReadinessState.READY_FOR_PAPER_OBSERVATION if not missing else ReadinessState.NOT_READY
        return CapabilityAudit(state=state, checks=checks, matrix=CAPABILITY_MATRIX, missing_capabilities=missing)

    async def _check_dexscreener(self, live: bool) -> ProviderCheck:
        if not self.settings.dexscreener_enabled:
            return ProviderCheck("DEX Screener", "discovery/quotes", ProviderStatus.NOT_CONFIGURED, action="enable DEXSCREENER_ENABLED")
        if not live:
            return ProviderCheck("DEX Screener", "discovery/quotes", ProviderStatus.CHECKING)
        client = DexScreenerClient(self.settings)
        start = perf_counter()
        try:
            payload = await client.request("/token-profiles/latest/v1")
            if not isinstance(payload, list):
                return ProviderCheck("DEX Screener", "discovery/quotes", ProviderStatus.SCHEMA_CHANGED, error="expected list")
            return ProviderCheck("DEX Screener", "discovery/quotes", ProviderStatus.HEALTHY, int((perf_counter() - start) * 1000), last_success_at=datetime.now(timezone.utc))
        except httpx.HTTPStatusError as exc:
            return self._http_error("DEX Screener", "discovery/quotes", exc)
        except Exception as exc:
            return ProviderCheck("DEX Screener", "discovery/quotes", ProviderStatus.OFFLINE, error=type(exc).__name__, action="check network/DNS/provider availability")
        finally:
            await client.close()

    async def _check_geckoterminal(self, live: bool) -> ProviderCheck:
        if not self.settings.geckoterminal_enabled:
            return ProviderCheck("GeckoTerminal", "OHLCV", ProviderStatus.NOT_CONFIGURED, action="enable GECKOTERMINAL_ENABLED")
        if not live:
            return ProviderCheck("GeckoTerminal", "OHLCV", ProviderStatus.CHECKING)
        client = GeckoTerminalClient(self.settings)
        start = perf_counter()
        try:
            payload = await client.network_pools(page=1)
            if not isinstance(payload, dict) or "data" not in payload:
                return ProviderCheck("GeckoTerminal", "OHLCV", ProviderStatus.SCHEMA_CHANGED, error="missing data")
            return ProviderCheck("GeckoTerminal", "OHLCV", ProviderStatus.HEALTHY, int((perf_counter() - start) * 1000), last_success_at=datetime.now(timezone.utc))
        except httpx.HTTPStatusError as exc:
            return self._http_error("GeckoTerminal", "OHLCV", exc)
        except Exception as exc:
            return ProviderCheck("GeckoTerminal", "OHLCV", ProviderStatus.OFFLINE, error=type(exc).__name__, action="check network/DNS/provider availability")
        finally:
            await client.close()

    @staticmethod
    def _configured(provider: str, capability: str, configured: bool, required: bool) -> ProviderCheck:
        if configured:
            return ProviderCheck(provider, capability, ProviderStatus.HEALTHY, last_success_at=datetime.now(timezone.utc))
        return ProviderCheck(provider, capability, ProviderStatus.NOT_CONFIGURED, action=f"provide {provider} configuration" if required else "optional")

    @staticmethod
    def _http_error(provider: str, capability: str, exc: httpx.HTTPStatusError) -> ProviderCheck:
        code = exc.response.status_code
        if code in {401, 403}:
            return ProviderCheck(provider, capability, ProviderStatus.AUTH_FAILED, error=str(code), action="verify key/header")
        if code == 429:
            return ProviderCheck(provider, capability, ProviderStatus.RATE_LIMITED, error=str(code), action="wait or upgrade quota")
        if code >= 500:
            return ProviderCheck(provider, capability, ProviderStatus.DEGRADED, error=str(code), action="retry later")
        return ProviderCheck(provider, capability, ProviderStatus.OFFLINE, error=str(code), action="inspect endpoint")

    @staticmethod
    async def _persist(session: AsyncSession, check: ProviderCheck) -> None:
        row = await session.scalar(
            select(ProviderHealthRecord).where(
                ProviderHealthRecord.provider == check.provider,
                ProviderHealthRecord.capability == check.capability,
            )
        )
        if row is None:
            row = ProviderHealthRecord(provider=check.provider, capability=check.capability, status=check.status.value)
        row.status = check.status.value
        row.latency_ms = check.latency_ms
        row.last_success_at = check.last_success_at
        row.last_error = check.error
        row.consecutive_failures = 0 if check.status == ProviderStatus.HEALTHY else (row.consecutive_failures or 0) + 1
        session.add(row)
