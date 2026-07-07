from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import CandidateHistory, CandidateWallet, TokenQuality, WalletActivity, WalletPosition
from app.services.smart_money import aware, clamp


class CandidateScoringEngine:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def score_all(self) -> int:
        from app.pipeline.wallet_ingestion import SolanaWalletEvidenceProvider, StoredWalletEvidenceProvider
        from app.pipeline.wallet_pipeline import WalletPipelineManager

        provider = (
            SolanaWalletEvidenceProvider(self.session, self.settings)
            if self.settings.app_env == "production" and self.settings.candidate_live_ingestion_enabled
            else StoredWalletEvidenceProvider(self.session)
        )
        try:
            return await WalletPipelineManager(
                self.session,
                self,
                evidence_provider=provider,
                batch_size=self.settings.candidate_pipeline_batch_size,
            ).run_all()
        finally:
            await provider.close()

    async def score_wallet(self, wallet: CandidateWallet) -> Decimal:
        positions = await self._positions(wallet.id)
        closed = [item for item in positions if item.position_status == "CLOSED"]
        if not closed:
            return Decimal("0")
        transaction_size = clamp(self._avg([Decimal(item.maximum_position_size or 0) for item in positions]) / Decimal("1000"))
        consistency = clamp(Decimal(len(closed)) * Decimal("15"))
        early_entry = clamp(self._avg([Decimal(item.position_quality_score or 0) for item in closed]))
        token_quality = await self._token_quality_from_positions(positions)
        holding = self._holding_discipline(closed)
        network = await self._network_influence_from_positions(positions)
        weights = self.settings.candidate_score_weights
        return clamp(
            transaction_size * Decimal(str(weights["transaction_size"]))
            + consistency * Decimal(str(weights["consistency"]))
            + early_entry * Decimal(str(weights["early_entry"]))
            + token_quality * Decimal(str(weights["token_quality"]))
            + holding * Decimal(str(weights["holding_behaviour"]))
            + network * Decimal(str(weights["network_influence"]))
        )

    async def reputation_score(self, wallet: CandidateWallet) -> Decimal:
        positions = await self._positions(wallet.id)
        closed = [item for item in positions if item.position_status == "CLOSED"]
        if not closed:
            return Decimal("0")
        win_proxy = await self.historical_accuracy(wallet)
        returns = self._avg([Decimal(item.realized_roi or 0) for item in closed])
        consistency = clamp(Decimal(len(closed)) * Decimal("15"))
        quality = self._avg([Decimal(item.position_quality_score or 0) for item in closed])
        risk = clamp(Decimal("100") - self._avg([Decimal(item.maximum_drawdown or 0) for item in closed]))
        return clamp(win_proxy * Decimal("0.30") + clamp(returns + Decimal("50")) * Decimal("0.20") + consistency * Decimal("0.15") + quality * Decimal("0.20") + risk * Decimal("0.15"))

    async def historical_accuracy(self, wallet: CandidateWallet) -> Decimal:
        closed = [item for item in await self._positions(wallet.id) if item.position_status == "CLOSED"]
        if not closed:
            return Decimal("0")
        winners = sum(1 for item in closed if Decimal(item.realized_roi or 0) > 0)
        return clamp(Decimal(winners) / Decimal(len(closed)) * Decimal("100"))

    async def _positions(self, wallet_id: int) -> list[WalletPosition]:
        return list(
            (
                await self.session.scalars(
                    select(WalletPosition).where(WalletPosition.candidate_wallet_id == wallet_id)
                )
            ).all()
        )

    @staticmethod
    def _avg(values: list[Decimal]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")

    async def _history(self, wallet_id: int) -> list[CandidateHistory]:
        return list(
            (
                await self.session.scalars(
                    select(CandidateHistory).where(CandidateHistory.wallet_id == wallet_id).order_by(CandidateHistory.timestamp)
                )
            ).all()
        )

    @staticmethod
    def _transaction_size(history: list[CandidateHistory]) -> Decimal:
        total = sum((Decimal(item.usd_value or 0) for item in history), Decimal("0"))
        return clamp(total / Decimal("1000"))

    @staticmethod
    def _consistency(history: list[CandidateHistory]) -> Decimal:
        days = {item.timestamp.date() for item in history}
        return clamp(Decimal(len(days)) * Decimal("20"))

    @staticmethod
    def _early_entry(history: list[CandidateHistory]) -> Decimal:
        now = datetime.now(timezone.utc)
        recent = sum(1 for item in history if (now - aware(item.timestamp)).days <= 7)
        return clamp(Decimal(recent) / Decimal(max(len(history), 1)) * Decimal("100"))

    async def _token_quality(self, history: list[CandidateHistory]) -> Decimal:
        tokens = {item.token for item in history}
        if not tokens:
            return Decimal("0")
        quality = await self.session.scalar(
            select(func.avg(TokenQuality.quality_score)).where(TokenQuality.token_address.in_(tokens))
        )
        return Decimal(str(quality or 50))

    async def _token_quality_from_positions(self, positions: list[WalletPosition]) -> Decimal:
        tokens = {item.token_address for item in positions if item.token_address}
        if not tokens:
            return Decimal("0")
        quality = await self.session.scalar(
            select(func.avg(TokenQuality.quality_score)).where(TokenQuality.token_address.in_(tokens))
        )
        return Decimal(str(quality or 50))

    @staticmethod
    def _holding_behaviour(history: list[CandidateHistory]) -> Decimal:
        buys = sum(1 for item in history if item.action.lower() in {"buy", "swap", "accumulate", "stake"})
        sells = sum(1 for item in history if item.action.lower() in {"sell", "out"})
        return clamp(Decimal(max(buys - sells, 0)) / Decimal(max(len(history), 1)) * Decimal("100"))

    async def _network_influence(self, history: list[CandidateHistory]) -> Decimal:
        tokens = {item.token for item in history}
        if not tokens:
            return Decimal("0")
        aligned = await self.session.scalar(
            select(func.count(func.distinct(WalletActivity.wallet_id))).where(WalletActivity.token_address.in_(tokens))
        )
        return clamp(Decimal(str(aligned or 0)) * Decimal("25"))

    async def _network_influence_from_positions(self, positions: list[WalletPosition]) -> Decimal:
        tokens = {item.token_address for item in positions if item.token_address}
        if not tokens:
            return Decimal("0")
        aligned = await self.session.scalar(
            select(func.count(func.distinct(WalletActivity.wallet_id))).where(WalletActivity.token_address.in_(tokens))
        )
        return clamp(Decimal(str(aligned or 0)) * Decimal("25"))

    @staticmethod
    def _holding_discipline(positions: list[WalletPosition]) -> Decimal:
        if not positions:
            return Decimal("0")
        quality = [
            Decimal("100") if Decimal(item.holding_period or 0) >= 1 else Decimal("45")
            for item in positions
        ]
        return sum(quality, Decimal("0")) / Decimal(len(quality))
