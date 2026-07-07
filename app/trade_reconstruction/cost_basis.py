from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models import CandidateHistory
from app.pipeline.wallet_ingestion import STABLECOINS, decimal_or_none
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)
WRAPPED_SOL = "So11111111111111111111111111111111111111112"
ZERO = Decimal("0")


class TokenPriceProvider(Protocol):
    async def price(self, token: str) -> Decimal | None:
        ...

    async def close(self) -> None:
        ...


class DexScreenerTokenPriceProvider:
    def __init__(self, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.client = client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        self._cache: dict[str, Decimal | None] = {}

    async def price(self, token: str) -> Decimal | None:
        if token in self._cache:
            return self._cache[token]
        if token in STABLECOINS:
            self._cache[token] = Decimal("1")
            return self._cache[token]
        price = await self._dex_price(token)
        if price is None and token == WRAPPED_SOL:
            price = await self._dex_price("So11111111111111111111111111111111111111112")
        self._cache[token] = price
        return price

    async def _dex_price(self, token: str) -> Decimal | None:
        for path in (f"/tokens/v1/solana/{token}", f"/token-pairs/v1/solana/{token}"):
            try:
                payload = await self.client.request_json("GET", path)
            except Exception as exc:
                logger.info("cost_basis_price_lookup_failed", token=token, path=path, error=type(exc).__name__)
                continue
            pairs = payload if isinstance(payload, list) else payload.get("pairs", []) if isinstance(payload, dict) else []
            prices = [decimal_or_none(pair.get("priceUsd")) for pair in pairs if isinstance(pair, dict)]
            price = next((item for item in prices if item is not None and item > 0), None)
            if price is not None:
                return price
        return None

    async def close(self) -> None:
        await self.client.close()


class CostBasisEnrichmentEngine:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: TokenPriceProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider or DexScreenerTokenPriceProvider(settings)

    async def enrich_missing_history(self, limit: int | None = None) -> int:
        limit = limit or self.settings.cost_basis_enrichment_batch_size
        rows = list(
            (
                await self.session.scalars(
                    select(CandidateHistory)
                    .where(CandidateHistory.usd_value.is_(None), CandidateHistory.amount > 0)
                    .order_by(CandidateHistory.timestamp.desc(), CandidateHistory.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        enriched = 0
        for row in rows:
            price = await self.provider.price(row.token)
            if price is None or price <= 0:
                continue
            row.usd_value = Decimal(row.amount or 0) * price
            enriched += 1
        await self.session.commit()
        return enriched

    async def close(self) -> None:
        await self.provider.close()
