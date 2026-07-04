from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateHistory


class WalletHistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_candidate(self, wallet_id: int, limit: int = 100) -> list[CandidateHistory]:
        return list(
            (
                await self.session.scalars(
                    select(CandidateHistory)
                    .where(CandidateHistory.wallet_id == wallet_id)
                    .order_by(CandidateHistory.timestamp.desc(), CandidateHistory.id.desc())
                    .limit(limit)
                )
            ).all()
        )

