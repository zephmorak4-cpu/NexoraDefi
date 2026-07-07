from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.market_context.context_score import MarketContextScorer
from app.market_context.holder_analyzer import HolderAnalyzer
from app.market_context.liquidity_analyzer import LiquidityAnalyzer
from app.market_context.market_cap_analyzer import MarketCapAnalyzer
from app.market_context.market_snapshot import MarketSnapshot, growth
from app.market_context.token_age import TokenAgeAnalyzer
from app.market_context.volume_analyzer import VolumeAnalyzer
from app.market_context.wallet_consensus import WalletConsensusAnalyzer
from app.models import MarketContext, PriceHistory, Token, TokenGrowthMetric, WalletPosition
from app.services.smart_money import aware, clamp


class MarketSnapshotService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def snapshot(self, token_address: str, timestamp: datetime | None, fallback_price: Decimal | None = None) -> MarketSnapshot:
        token = await self._token(token_address)
        if token is None or timestamp is None:
            return MarketSnapshot(timestamp=timestamp, price=fallback_price)
        price = await self._price(token.id, timestamp)
        growth_metric = await self._growth(token.id, timestamp)
        token_age = None
        if token.created_at:
            token_age = Decimal(str((aware(timestamp) - aware(token.created_at)).total_seconds() / 86400))
        return MarketSnapshot(
            timestamp=timestamp,
            market_cap=Decimal(price.market_cap) if price and price.market_cap is not None else None,
            liquidity=Decimal(price.liquidity_value) if price and price.liquidity_value is not None else None,
            holder_count=int(growth_metric.holder_count) if growth_metric else None,
            daily_volume=Decimal(price.volume) if price and price.volume is not None else None,
            price=Decimal(price.price) if price and price.price is not None else fallback_price,
            token_age_days=token_age,
        )

    async def _token(self, token_address: str) -> Token | None:
        return await self.session.scalar(
            select(Token).where(Token.chain == "solana", Token.blockchain_address == token_address)
        )

    async def _price(self, token_id: int, timestamp: datetime) -> PriceHistory | None:
        return await self.session.scalar(
            select(PriceHistory)
            .where(PriceHistory.token_id == token_id, PriceHistory.timestamp <= timestamp)
            .order_by(PriceHistory.timestamp.desc(), PriceHistory.id.desc())
        )

    async def _growth(self, token_id: int, timestamp: datetime) -> TokenGrowthMetric | None:
        return await self.session.scalar(
            select(TokenGrowthMetric)
            .where(TokenGrowthMetric.token_id == token_id, TokenGrowthMetric.calculated_at <= timestamp)
            .order_by(TokenGrowthMetric.calculated_at.desc(), TokenGrowthMetric.id.desc())
        )


class MarketContextEngine:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.snapshots = MarketSnapshotService(session)
        self.consensus = WalletConsensusAnalyzer(session, settings)
        self.scorer = MarketContextScorer(settings)
        self.liquidity = LiquidityAnalyzer()
        self.holders = HolderAnalyzer()
        self.volume = VolumeAnalyzer()
        self.market_cap = MarketCapAnalyzer()
        self.age = TokenAgeAnalyzer()

    async def enrich_all_positions(self) -> int:
        positions = list(
            (
                await self.session.scalars(
                    select(WalletPosition)
                    .where(WalletPosition.candidate_wallet_id.is_not(None), WalletPosition.token_address.is_not(None))
                    .order_by(WalletPosition.updated_at.desc(), WalletPosition.id.desc())
                    .limit(self.settings.market_context_batch_size)
                )
            ).all()
        )
        enriched = 0
        for position in positions:
            await self.enrich_position(position)
            enriched += 1
        await self.session.commit()
        return enriched

    async def enrich_wallet_positions(self, wallet_id: int) -> int:
        positions = list(
            (
                await self.session.scalars(
                    select(WalletPosition).where(
                        WalletPosition.candidate_wallet_id == wallet_id,
                        WalletPosition.token_address.is_not(None),
                    )
                )
            ).all()
        )
        for position in positions:
            await self.enrich_position(position)
        return len(positions)

    async def enrich_position(self, position: WalletPosition) -> MarketContext:
        token_address = position.token_address or ""
        entry_snapshot = await self.snapshots.snapshot(
            token_address,
            position.entry_time,
            Decimal(position.average_entry_price) if position.average_entry_price else None,
        )
        exit_snapshot = await self.snapshots.snapshot(
            token_address,
            position.final_exit_time,
            Decimal(position.average_exit_price) if position.average_exit_price else None,
        )
        consensus = await self.consensus.analyze(token_address, position.entry_time)
        factors = self._factors(entry_snapshot, exit_snapshot, consensus.consensus_strength)
        context_score = self.scorer.score(factors)
        row = await self.session.scalar(
            select(MarketContext).where(MarketContext.wallet_position_id == position.id)
        )
        if row is None:
            row = MarketContext(wallet_position_id=position.id, token_address=token_address)
        row.token_address = token_address
        row.entry_timestamp = position.entry_time
        row.exit_timestamp = position.final_exit_time
        row.market_cap_entry = entry_snapshot.market_cap
        row.market_cap_exit = exit_snapshot.market_cap
        row.liquidity_entry = entry_snapshot.liquidity
        row.liquidity_exit = exit_snapshot.liquidity
        row.holder_count_entry = entry_snapshot.holder_count
        row.holder_count_exit = exit_snapshot.holder_count
        row.daily_volume_entry = entry_snapshot.daily_volume
        row.daily_volume_exit = exit_snapshot.daily_volume
        row.token_age_entry = entry_snapshot.token_age_days
        row.token_age_exit = exit_snapshot.token_age_days
        row.price_entry = entry_snapshot.price
        row.price_exit = exit_snapshot.price
        row.wallet_consensus = consensus.label()
        row.context_score = context_score
        row.market_sentiment = self._sentiment(context_score)
        self.session.add(row)
        return row

    def _factors(
        self,
        entry: MarketSnapshot,
        exit: MarketSnapshot,
        consensus_strength: Decimal,
    ) -> dict[str, Decimal | None]:
        liquidity_growth = growth(entry.liquidity, exit.liquidity)
        market_cap_growth = growth(entry.market_cap, exit.market_cap)
        volume_growth = growth(entry.daily_volume, exit.daily_volume)
        holder_growth = growth(entry.holder_count, exit.holder_count)
        market_structure = self._market_structure(entry, exit)
        return {
            "liquidity": self.liquidity.score(entry.liquidity, liquidity_growth),
            "market_cap": self.market_cap.score(entry.market_cap, market_cap_growth),
            "volume_trend": self.volume.score(entry.daily_volume, volume_growth),
            "holder_growth": self.holders.score(entry.holder_count, holder_growth),
            "consensus": consensus_strength,
            "token_age": self.age.score(entry.token_age_days),
            "market_structure": market_structure,
        }

    @staticmethod
    def _market_structure(entry: MarketSnapshot, exit: MarketSnapshot) -> Decimal | None:
        price_growth = growth(entry.price, exit.price)
        liquidity_growth = growth(entry.liquidity, exit.liquidity)
        if price_growth is None and liquidity_growth is None:
            return None
        score = Decimal("50")
        if price_growth is not None:
            score += min(price_growth, Decimal("100")) * Decimal("0.35")
        if liquidity_growth is not None:
            score += min(liquidity_growth, Decimal("100")) * Decimal("0.25")
        return clamp(score)

    @staticmethod
    def _sentiment(score: Decimal | None) -> str:
        if score is None:
            return "Insufficient Market Data"
        if score >= 80:
            return "Strong Supportive Context"
        if score >= 60:
            return "Supportive Context"
        if score >= 40:
            return "Mixed Context"
        return "Weak Context"


def explain_market_context(context: MarketContext | None) -> str:
    if context is None or context.context_score is None:
        return "Insufficient Market Data"
    if Decimal(context.context_score) >= Decimal("70"):
        return (
            "This wallet entered while market context was supportive: liquidity, volume, holder growth, "
            "or wallet consensus showed enough confirmation to strengthen the trade thesis."
        )
    if Decimal(context.context_score) >= Decimal("45"):
        return (
            "This trade had mixed market context. Some market structure evidence supported the entry, "
            "but confirmation was not broad enough to classify it as a strong context trade."
        )
    return (
        "This trade had weak market context. Available market data did not show enough liquidity, growth, "
        "or elite-wallet consensus to explain the position as high quality."
    )
