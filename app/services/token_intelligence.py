from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import pstdev

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models import (
    MomentumMetric,
    PriceHistory,
    SmartMoneySignal,
    Token,
    TokenGrowthMetric,
    Transaction,
)
from app.services.smart_money import HUNDRED, ZERO, aware, clamp

logger = get_logger(__name__)
POSITIVE_SMART_MONEY_SIGNALS = ("ELITE_ENTRY", "ACCUMULATION", "SMART_MONEY_CLUSTER")


def percentage_change(current: Decimal | int | None, previous: Decimal | int | None) -> Decimal:
    if current is None or previous is None or Decimal(str(previous)) == 0:
        return ZERO
    return (Decimal(str(current)) - Decimal(str(previous))) / abs(Decimal(str(previous))) * HUNDRED


def normalized_growth(value: Decimal | float) -> Decimal:
    return clamp(Decimal("50") + Decimal(str(value)) / 2)


class TokenGrowthAnalyzer:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def _baseline(self, token_id: int, target: datetime) -> TokenGrowthMetric | None:
        return await self.session.scalar(
            select(TokenGrowthMetric)
            .where(
                TokenGrowthMetric.token_id == token_id,
                TokenGrowthMetric.calculated_at <= target,
            )
            .order_by(TokenGrowthMetric.calculated_at.desc())
            .limit(1)
        )

    @staticmethod
    def adoption_score(metric: TokenGrowthMetric) -> Decimal:
        return clamp(
            normalized_growth(metric.holder_growth_24h) * Decimal("0.30")
            + normalized_growth(metric.holder_growth_7d) * Decimal("0.25")
            + normalized_growth(metric.transaction_growth_24h) * Decimal("0.25")
            + normalized_growth(metric.transaction_growth_7d) * Decimal("0.20")
        )

    @staticmethod
    def growth_score(metric: TokenGrowthMetric) -> Decimal:
        return clamp(
            normalized_growth(metric.volume_growth_24h) * Decimal("0.30")
            + normalized_growth(metric.volume_growth_7d) * Decimal("0.25")
            + normalized_growth(metric.market_cap_growth_24h) * Decimal("0.25")
            + normalized_growth(metric.market_cap_growth_7d) * Decimal("0.20")
        )

    @staticmethod
    def liquidity_score(metric: TokenGrowthMetric) -> Decimal:
        if metric.liquidity_value is None or Decimal(metric.liquidity_value) <= 0:
            return ZERO
        size = clamp(Decimal(str(math.log10(float(metric.liquidity_value) + 1))) * Decimal("12.5"))
        growth = (
            normalized_growth(metric.liquidity_growth_24h) * Decimal("0.6")
            + normalized_growth(metric.liquidity_growth_7d) * Decimal("0.4")
        )
        return clamp(size * Decimal("0.65") + growth * Decimal("0.35"))

    async def analyze_token(self, token_id: int, now: datetime | None = None) -> TokenGrowthMetric:
        now = aware(now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
        existing = await self.session.scalar(
            select(TokenGrowthMetric).where(
                TokenGrowthMetric.token_id == token_id,
                TokenGrowthMetric.calculated_at == now,
            )
        )
        if existing:
            return existing

        holder_count = await self.session.scalar(
            select(func.count(func.distinct(Transaction.wallet_id))).where(
                Transaction.token_id == token_id
            )
        )
        transaction_count = await self.session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.token_id == token_id,
                Transaction.timestamp >= now - timedelta(hours=24),
            )
        )
        market = await self.session.scalar(
            select(PriceHistory)
            .where(PriceHistory.token_id == token_id, PriceHistory.timestamp <= now)
            .order_by(PriceHistory.timestamp.desc())
            .limit(1)
        )
        baseline_24h = await self._baseline(token_id, now - timedelta(hours=24))
        baseline_7d = await self._baseline(token_id, now - timedelta(days=7))
        current = {
            "holder_count": int(holder_count or 0),
            "transaction_count": int(transaction_count or 0),
            "volume_24h": Decimal(market.volume) if market and market.volume is not None else None,
            "market_cap": Decimal(market.market_cap) if market and market.market_cap is not None else None,
            "liquidity_value": Decimal(market.liquidity_value) if market and market.liquidity_value is not None else None,
        }

        def baseline_value(snapshot: TokenGrowthMetric | None, field: str):
            return getattr(snapshot, field) if snapshot else None

        metric = TokenGrowthMetric(
            token_id=token_id,
            **current,
            holder_growth_24h=percentage_change(current["holder_count"], baseline_value(baseline_24h, "holder_count")),
            holder_growth_7d=percentage_change(current["holder_count"], baseline_value(baseline_7d, "holder_count")),
            transaction_growth_24h=percentage_change(current["transaction_count"], baseline_value(baseline_24h, "transaction_count")),
            transaction_growth_7d=percentage_change(current["transaction_count"], baseline_value(baseline_7d, "transaction_count")),
            volume_growth_24h=percentage_change(current["volume_24h"], baseline_value(baseline_24h, "volume_24h")),
            volume_growth_7d=percentage_change(current["volume_24h"], baseline_value(baseline_7d, "volume_24h")),
            market_cap_growth_24h=percentage_change(current["market_cap"], baseline_value(baseline_24h, "market_cap")),
            market_cap_growth_7d=percentage_change(current["market_cap"], baseline_value(baseline_7d, "market_cap")),
            liquidity_growth_24h=percentage_change(current["liquidity_value"], baseline_value(baseline_24h, "liquidity_value")),
            liquidity_growth_7d=percentage_change(current["liquidity_value"], baseline_value(baseline_7d, "liquidity_value")),
            calculated_at=now,
        )
        self.session.add(metric)
        await self.session.flush()
        return metric

    async def analyze_all(self) -> int:
        processed = 0
        cursor = 0
        now = datetime.now(timezone.utc)
        while True:
            token_ids = (
                await self.session.scalars(
                    select(Token.id)
                    .where(Token.id > cursor)
                    .order_by(Token.id)
                    .limit(self.settings.token_intelligence_batch_size)
                )
            ).all()
            if not token_ids:
                break
            for token_id in token_ids:
                await self.analyze_token(token_id, now)
                processed += 1
            await self.session.commit()
            cursor = token_ids[-1]
        logger.info("token_growth_analysis_complete", tokens=processed)
        return processed


class MomentumAnalyzer:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    @staticmethod
    def momentum_score(
        price_change_1h: Decimal,
        price_change_24h: Decimal,
        price_change_7d: Decimal,
        price_change_30d: Decimal,
        volume_growth_24h: Decimal,
        volatility_score: Decimal,
    ) -> Decimal:
        price_score = (
            normalized_growth(price_change_1h) * Decimal("0.15")
            + normalized_growth(price_change_24h) * Decimal("0.25")
            + normalized_growth(price_change_7d) * Decimal("0.35")
            + normalized_growth(price_change_30d) * Decimal("0.25")
        )
        confirmed = price_score * Decimal("0.80") + normalized_growth(volume_growth_24h) * Decimal("0.20")
        volatility_penalty = max(ZERO, volatility_score - Decimal("60")) * Decimal("0.5")
        return clamp(confirmed - volatility_penalty)

    def classify_stage(
        self,
        price_change_24h: Decimal,
        price_change_7d: Decimal,
        price_change_30d: Decimal,
        volume_growth_24h: Decimal,
        transaction_growth_24h: Decimal,
        volatility_score: Decimal,
        smart_entries: int,
        smart_exits: int,
    ) -> str:
        if (
            price_change_24h >= Decimal(str(self.settings.momentum_overheated_24h_threshold))
            or price_change_7d >= Decimal(str(self.settings.momentum_overheated_7d_threshold))
            or volatility_score >= Decimal(str(self.settings.momentum_volatility_overheated_threshold))
            or (
                volume_growth_24h >= Decimal(str(self.settings.momentum_volume_spike_threshold))
                and price_change_24h > 10
            )
        ):
            return "OVERHEATED"
        if price_change_24h < 0 and (
            volume_growth_24h < 0 or transaction_growth_24h < 0 or smart_exits > smart_entries
        ):
            return "DECLINING"
        if 0 < price_change_24h < 10 and volume_growth_24h > 0 and smart_entries > smart_exits:
            return "EARLY"
        if price_change_7d >= 15 and price_change_30d >= 20 and volume_growth_24h >= 0:
            return "TRENDING"
        if price_change_24h >= 5 and price_change_7d >= 10 and volume_growth_24h > 0:
            return "ACCELERATING"
        return "EARLY" if price_change_24h >= 0 else "DECLINING"

    async def _price_at(self, token_id: int, target: datetime) -> Decimal | None:
        value = await self.session.scalar(
            select(PriceHistory.price)
            .where(PriceHistory.token_id == token_id, PriceHistory.timestamp <= target)
            .order_by(PriceHistory.timestamp.desc())
            .limit(1)
        )
        return Decimal(value) if value is not None else None

    async def analyze_token(self, token_id: int, now: datetime | None = None) -> MomentumMetric:
        now = aware(now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
        existing = await self.session.scalar(
            select(MomentumMetric).where(
                MomentumMetric.token_id == token_id, MomentumMetric.calculated_at == now
            )
        )
        if existing:
            return existing
        current = await self._price_at(token_id, now)
        changes: dict[str, Decimal] = {}
        for name, delta in (
            ("1h", timedelta(hours=1)),
            ("24h", timedelta(hours=24)),
            ("7d", timedelta(days=7)),
            ("30d", timedelta(days=30)),
        ):
            changes[name] = percentage_change(current, await self._price_at(token_id, now - delta))

        recent_prices = list(
            (
                await self.session.scalars(
                    select(PriceHistory.price)
                    .where(
                        PriceHistory.token_id == token_id,
                        PriceHistory.timestamp >= now - timedelta(days=7),
                        PriceHistory.timestamp <= now,
                    )
                    .order_by(PriceHistory.timestamp.desc())
                    .limit(1000)
                )
            ).all()
        )
        returns = [
            (float(recent_prices[index - 1]) - float(recent_prices[index])) / float(recent_prices[index]) * 100
            for index in range(1, len(recent_prices))
            if recent_prices[index]
        ]
        volatility = clamp(Decimal(str(pstdev(returns))) * Decimal("5")) if len(returns) > 1 else ZERO
        growth = await self.session.scalar(
            select(TokenGrowthMetric)
            .where(TokenGrowthMetric.token_id == token_id, TokenGrowthMetric.calculated_at <= now)
            .order_by(TokenGrowthMetric.calculated_at.desc())
            .limit(1)
        )
        volume_growth = Decimal(growth.volume_growth_24h or 0) if growth else ZERO
        transaction_growth = Decimal(growth.transaction_growth_24h or 0) if growth else ZERO
        smart_rows = (
            await self.session.execute(
                select(SmartMoneySignal.signal_type, func.count(SmartMoneySignal.id))
                .where(
                    SmartMoneySignal.token_id == token_id,
                    SmartMoneySignal.created_at >= now - timedelta(days=7),
                )
                .group_by(SmartMoneySignal.signal_type)
            )
        ).all()
        counts = dict(smart_rows)
        entries = sum(int(counts.get(kind, 0)) for kind in POSITIVE_SMART_MONEY_SIGNALS)
        exits = int(counts.get("SMART_MONEY_EXIT", 0))
        score = self.momentum_score(
            changes["1h"], changes["24h"], changes["7d"], changes["30d"], volume_growth, volatility
        )
        stage = self.classify_stage(
            changes["24h"], changes["7d"], changes["30d"], volume_growth,
            transaction_growth, volatility, entries, exits,
        )
        metric = MomentumMetric(
            token_id=token_id,
            price_change_1h=changes["1h"],
            price_change_24h=changes["24h"],
            price_change_7d=changes["7d"],
            price_change_30d=changes["30d"],
            volatility_score=volatility,
            momentum_score=score,
            momentum_stage=stage,
            calculated_at=now,
        )
        self.session.add(metric)
        await self.session.flush()
        return metric

    async def analyze_all(self) -> int:
        processed = 0
        cursor = 0
        now = datetime.now(timezone.utc)
        while True:
            token_ids = (
                await self.session.scalars(
                    select(Token.id)
                    .where(Token.id > cursor)
                    .order_by(Token.id)
                    .limit(self.settings.token_intelligence_batch_size)
                )
            ).all()
            if not token_ids:
                break
            for token_id in token_ids:
                await self.analyze_token(token_id, now)
                processed += 1
            await self.session.commit()
            cursor = token_ids[-1]
        logger.info("momentum_analysis_complete", tokens=processed)
        return processed

