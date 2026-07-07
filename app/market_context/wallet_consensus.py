from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import CandidateHistory, CandidateWallet, TrackedWallet, WalletActivity
from app.services.smart_money import aware, clamp


@dataclass(frozen=True)
class ConsensusResult:
    elite_before: int
    elite_after: int
    candidate_before: int
    candidate_after: int
    average_entry_delay_hours: Decimal | None
    consensus_strength: Decimal

    def label(self) -> str:
        if self.elite_before + self.candidate_before + self.elite_after + self.candidate_after == 0:
            return "Insufficient Market Data"
        return (
            f"Elite before: {self.elite_before}, elite after: {self.elite_after}, "
            f"candidate before: {self.candidate_before}, candidate after: {self.candidate_after}, "
            f"strength: {self.consensus_strength:.2f}/100"
        )


class WalletConsensusAnalyzer:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def analyze(self, token_address: str, entry_time: datetime | None) -> ConsensusResult:
        if entry_time is None:
            return ConsensusResult(0, 0, 0, 0, None, Decimal("0"))
        entry = aware(entry_time)
        elite_before = await self._elite_count(token_address, before=entry)
        elite_after = await self._elite_count(token_address, after=entry)
        candidate_before = await self._candidate_count(token_address, before=entry)
        candidate_after = await self._candidate_count(token_address, after=entry)
        delays = await self._entry_delays(token_address, entry)
        avg_delay = sum(delays, Decimal("0")) / Decimal(len(delays)) if delays else None
        strength = clamp(
            Decimal(elite_before) * Decimal("30")
            + Decimal(elite_after) * Decimal("18")
            + Decimal(candidate_before) * Decimal("14")
            + Decimal(candidate_after) * Decimal("8")
        )
        return ConsensusResult(elite_before, elite_after, candidate_before, candidate_after, avg_delay, strength)

    async def _elite_count(self, token: str, before: datetime | None = None, after: datetime | None = None) -> int:
        query = (
            select(func.count(distinct(TrackedWallet.wallet_address)))
            .join(WalletActivity, WalletActivity.wallet_id == TrackedWallet.id)
            .where(
                TrackedWallet.status == "active",
                TrackedWallet.reputation_score >= self.settings.candidate_promotion_reputation,
                WalletActivity.token_address == token,
            )
        )
        if before is not None:
            query = query.where(WalletActivity.timestamp < before)
        if after is not None:
            query = query.where(WalletActivity.timestamp >= after)
        return int(await self.session.scalar(query) or 0)

    async def _candidate_count(self, token: str, before: datetime | None = None, after: datetime | None = None) -> int:
        query = (
            select(func.count(distinct(CandidateWallet.wallet_address)))
            .join(CandidateHistory, CandidateHistory.wallet_id == CandidateWallet.id)
            .where(
                CandidateWallet.candidate_score >= self.settings.candidate_promotion_score,
                CandidateHistory.token == token,
            )
        )
        if before is not None:
            query = query.where(CandidateHistory.timestamp < before)
        if after is not None:
            query = query.where(CandidateHistory.timestamp >= after)
        return int(await self.session.scalar(query) or 0)

    async def _entry_delays(self, token: str, entry: datetime) -> list[Decimal]:
        rows = (
            await self.session.scalars(
                select(WalletActivity.timestamp)
                .join(TrackedWallet, TrackedWallet.id == WalletActivity.wallet_id)
                .where(WalletActivity.token_address == token, WalletActivity.timestamp >= entry)
                .limit(50)
            )
        ).all()
        return [Decimal(str((aware(row) - entry).total_seconds() / 3600)) for row in rows]
