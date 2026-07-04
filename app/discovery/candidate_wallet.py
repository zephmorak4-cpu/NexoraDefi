from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateHistory, CandidateWallet


class DiscoveryEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str
    token: str
    action: str
    amount: Decimal = Decimal("0")
    usd_value: Decimal | None = None
    timestamp: datetime
    reason: str
    chain: str = "solana"


class CandidateWalletRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_event(self, event: DiscoveryEvent) -> bool:
        wallet = await self.session.scalar(
            select(CandidateWallet).where(
                CandidateWallet.chain == event.chain,
                CandidateWallet.wallet_address == event.wallet_address,
            )
        )
        is_new = wallet is None
        if wallet is None:
            wallet = CandidateWallet(
                wallet_address=event.wallet_address,
                chain=event.chain,
                first_seen=event.timestamp,
                discovery_reason=event.reason,
                status="observing",
            )
            self.session.add(wallet)
            await self.session.flush()
        wallet.last_seen = event.timestamp
        wallet.discovery_reason = event.reason
        self.session.add(
            CandidateHistory(
                wallet_id=wallet.id,
                token=event.token,
                action=event.action,
                amount=event.amount,
                usd_value=event.usd_value,
                timestamp=event.timestamp,
            )
        )
        return is_new

    async def candidates(self, statuses: tuple[str, ...] = ("observing",)) -> list[CandidateWallet]:
        return list(
            (
                await self.session.scalars(
                    select(CandidateWallet)
                    .where(CandidateWallet.status.in_(statuses))
                    .order_by(CandidateWallet.candidate_score.desc(), CandidateWallet.last_seen.desc())
                )
            ).all()
        )

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

