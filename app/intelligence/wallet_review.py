from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.wallet_promotion import WalletPromotionService
from app.models import CandidateWallet, WalletReview
from app.core.config import Settings


class WalletReviewService:
    VALID_STATUSES = {"Pending", "Approved", "Rejected", "Needs Observation"}

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def ensure_review(self, wallet_id: int) -> WalletReview:
        review = await self.session.scalar(select(WalletReview).where(WalletReview.wallet_id == wallet_id))
        if review is None:
            review = WalletReview(wallet_id=wallet_id, review_status="Pending", approved_for_signals=False)
            self.session.add(review)
            await self.session.flush()
        return review

    async def approve(self, wallet_id: int, reviewed_by: str | None = None, notes: str | None = None) -> WalletReview:
        wallet = await self._wallet(wallet_id)
        review = await self.ensure_review(wallet_id)
        review.review_status = "Approved"
        review.review_notes = notes
        review.reviewed_by = reviewed_by
        review.reviewed_at = datetime.now(timezone.utc)
        review.approved_for_signals = True
        await WalletPromotionService(self.session, self.settings).promote(wallet)
        await self.session.commit()
        return review

    async def reject(self, wallet_id: int, reviewed_by: str | None = None, notes: str | None = None) -> WalletReview:
        wallet = await self._wallet(wallet_id)
        review = await self.ensure_review(wallet_id)
        review.review_status = "Rejected"
        review.review_notes = notes
        review.reviewed_by = reviewed_by
        review.reviewed_at = datetime.now(timezone.utc)
        review.approved_for_signals = False
        wallet.status = "rejected"
        await self.session.commit()
        return review

    async def needs_observation(self, wallet_id: int, reviewed_by: str | None = None, notes: str | None = None) -> WalletReview:
        wallet = await self._wallet(wallet_id)
        review = await self.ensure_review(wallet_id)
        review.review_status = "Needs Observation"
        review.review_notes = notes
        review.reviewed_by = reviewed_by
        review.reviewed_at = datetime.now(timezone.utc)
        review.approved_for_signals = False
        wallet.status = "observing"
        await self.session.commit()
        return review

    async def _wallet(self, wallet_id: int) -> CandidateWallet:
        wallet = await self.session.get(CandidateWallet, wallet_id)
        if wallet is None:
            raise ValueError("candidate wallet not found")
        return wallet
