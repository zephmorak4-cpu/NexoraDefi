from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import CandidateWallet, TrackedWallet
from app.services.smart_money import aware


class WalletPromotionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def evaluate_promotions(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.candidate_observation_days)
        candidates = [
            candidate
            for candidate in (
                await self.session.scalars(
                    select(CandidateWallet).where(
                        CandidateWallet.status == "observing",
                        CandidateWallet.candidate_score >= self.settings.candidate_promotion_score,
                        CandidateWallet.reputation_score >= self.settings.candidate_promotion_reputation,
                        CandidateWallet.historical_accuracy_score >= self.settings.candidate_historical_accuracy_threshold,
                        CandidateWallet.suspicious_score <= self.settings.candidate_max_suspicious_score,
                    )
                )
            ).all()
            if aware(candidate.first_seen) <= cutoff
        ]
        promoted = 0
        for candidate in candidates:
            promoted += int(await self.promote(candidate))
        await self.session.commit()
        return promoted

    async def promote(self, candidate: CandidateWallet) -> bool:
        tracked = await self.session.scalar(
            select(TrackedWallet).where(
                TrackedWallet.chain == candidate.chain,
                TrackedWallet.wallet_address == candidate.wallet_address,
            )
        )
        if tracked is None:
            tracked = TrackedWallet(wallet_address=candidate.wallet_address, chain=candidate.chain)
            self.session.add(tracked)
            await self.session.flush()
        tracked.wallet_label = candidate.wallet_type
        tracked.wallet_category = "smart_money"
        tracked.source = "discovery"
        tracked.status = "active"
        tracked.notes = f"Promoted from candidate pool: {candidate.discovery_reason}"
        tracked.reputation_score = candidate.reputation_score
        candidate.status = "promoted"
        return True

    async def reject(self, candidate: CandidateWallet, notes: str | None = None) -> None:
        candidate.status = "rejected"
        if notes:
            candidate.notes = notes
        await self.session.commit()

    async def evaluate_demotions(self) -> int:
        wallets = list(
            (
                await self.session.scalars(
                    select(TrackedWallet).where(
                        TrackedWallet.status == "active",
                        TrackedWallet.reputation_score < self.settings.candidate_demotion_reputation,
                    )
                )
            ).all()
        )
        demoted = 0
        for wallet in wallets:
            wallet.status = "observing"
            candidate = await self.session.scalar(
                select(CandidateWallet).where(
                    CandidateWallet.chain == wallet.chain,
                    CandidateWallet.wallet_address == wallet.wallet_address,
                )
            )
            if candidate is None:
                candidate = CandidateWallet(
                    wallet_address=wallet.wallet_address,
                    chain=wallet.chain,
                    discovery_reason="demoted_elite_wallet",
                    status="observing",
                )
                self.session.add(candidate)
            else:
                candidate.status = "observing"
                candidate.notes = "Demoted from elite wallet monitoring after reputation deterioration."
            demoted += 1
        await self.session.commit()
        return demoted
