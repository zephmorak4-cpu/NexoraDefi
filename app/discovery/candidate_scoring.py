from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import CandidateHistory, CandidateWallet, TokenQuality, WalletActivity
from app.services.smart_money import aware, clamp


class CandidateScoringEngine:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def score_all(self) -> int:
        from app.pipeline.wallet_pipeline import WalletPipelineManager

        return await WalletPipelineManager(self.session, self).run_all()

    async def score_wallet(self, wallet: CandidateWallet) -> Decimal:
        history = await self._history(wallet.id)
        if not history:
            return Decimal("0")
        transaction_size = self._transaction_size(history)
        consistency = self._consistency(history)
        early_entry = self._early_entry(history)
        token_quality = await self._token_quality(history)
        holding = self._holding_behaviour(history)
        network = await self._network_influence(history)
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
        history = await self._history(wallet.id)
        if not history:
            return Decimal("0")
        win_proxy = await self.historical_accuracy(wallet)
        size = self._transaction_size(history)
        consistency = self._consistency(history)
        quality = await self._token_quality(history)
        return clamp(win_proxy * Decimal("0.35") + size * Decimal("0.25") + consistency * Decimal("0.20") + quality * Decimal("0.20"))

    async def historical_accuracy(self, wallet: CandidateWallet) -> Decimal:
        history = await self._history(wallet.id)
        if not history:
            return Decimal("0")
        good_actions = sum(1 for item in history if item.action.lower() in {"buy", "swap", "accumulate", "liquidity_add", "stake"})
        return clamp(Decimal(good_actions) / Decimal(len(history)) * Decimal("100"))

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
