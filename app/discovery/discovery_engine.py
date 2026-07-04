from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.discovery.candidate_wallet import CandidateWalletRepository, DiscoveryEvent
from app.discovery.wallet_history import WalletHistoryService
from app.discovery.wallet_classifier import WalletClassifier
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)


class DiscoverySource(Protocol):
    async def events(self) -> list[DiscoveryEvent]:
        ...

    async def close(self) -> None:
        ...


class SolanaDiscoverySource:
    def __init__(
        self,
        settings: Settings,
        dexscreener_client: AsyncAPIClient | None = None,
        moralis_client: AsyncAPIClient | None = None,
    ) -> None:
        self.settings = settings
        self.dexscreener_client = dexscreener_client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        self.moralis_client = moralis_client or AsyncAPIClient(
            "https://solana-gateway.moralis.io",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            headers={"accept": "application/json", "X-API-Key": settings.moralis_api_key or ""},
        )

    async def events(self) -> list[DiscoveryEvent]:
        if not self.settings.moralis_api_key:
            return []
        profiles = await self.dexscreener_client.request_json("GET", "/token-profiles/latest/v1")
        items = profiles if isinstance(profiles, list) else [profiles] if isinstance(profiles, dict) else []
        events: list[DiscoveryEvent] = []
        for profile in items[: self.settings.discovery_token_scan_limit]:
            if not isinstance(profile, dict) or profile.get("chainId") != "solana" or not profile.get("tokenAddress"):
                continue
            events.extend(await self._token_events(str(profile["tokenAddress"]), "interaction_with_trending_token"))
        return events

    async def _token_events(self, token_address: str, reason: str) -> list[DiscoveryEvent]:
        payload = await self.moralis_client.request_json(
            "GET",
            f"/token/mainnet/{token_address}/transfers",
            params={"limit": self.settings.discovery_transfer_limit},
            headers={"X-API-Key": self.settings.moralis_api_key or ""},
        )
        raw_items = payload.get("result", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            return []
        events = []
        for item in raw_items:
            event = self._normalize_event(item, token_address, reason)
            if event is not None and self._passes_initial_filters(event):
                events.append(event)
        return events

    def _passes_initial_filters(self, event: DiscoveryEvent) -> bool:
        return bool(
            event.wallet_address
            and event.wallet_address not in self.settings.discovery_blacklisted_wallets
            and (event.usd_value or Decimal("0")) >= Decimal(str(self.settings.discovery_min_usd_value))
        )

    @classmethod
    def _normalize_event(cls, item: dict[str, Any], token_address: str, reason: str) -> DiscoveryEvent | None:
        wallet = item.get("owner") or item.get("from_address") or item.get("to_address") or item.get("walletAddress")
        if not wallet:
            return None
        timestamp_raw = item.get("blockTimestamp") or item.get("block_timestamp") or item.get("timestamp")
        if isinstance(timestamp_raw, str):
            timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        else:
            timestamp = datetime.fromtimestamp(int(timestamp_raw or datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
        usd_value = cls._decimal_or_none(item.get("usdValue") or item.get("usd_value") or item.get("valueUsd"))
        return DiscoveryEvent(
            wallet_address=str(wallet),
            token=str(item.get("tokenAddress") or item.get("mint") or token_address),
            action=str(item.get("type") or item.get("transactionType") or "swap").lower(),
            amount=cls._decimal_or_zero(item.get("amount") or item.get("value")),
            usd_value=usd_value,
            timestamp=timestamp,
            reason=reason,
        )

    @staticmethod
    def _decimal_or_zero(value: Any) -> Decimal:
        return Decimal(str(value or "0"))

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        return None if value is None or value == "" else Decimal(str(value))

    async def close(self) -> None:
        await self.dexscreener_client.close()
        await self.moralis_client.close()


class DiscoveryEngine:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        source: DiscoverySource | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.source = source or SolanaDiscoverySource(settings)
        self.repository = CandidateWalletRepository(session)
        self.classifier = WalletClassifier()

    async def discover(self) -> int:
        events = await self.source.events()
        stored = 0
        for event in events:
            stored += int(await self.repository.upsert_event(event))
        history = WalletHistoryService(self.session)
        for wallet in await self.repository.candidates(statuses=("observing",)):
            wallet.wallet_type = self.classifier.classify(await history.for_candidate(wallet.id))
        await self.session.commit()
        logger.info("candidate_wallet_discovery_complete", events=len(events), new_candidates=stored)
        return stored

    async def close(self) -> None:
        await self.source.close()
