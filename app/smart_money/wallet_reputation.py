from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TrackedWallet, WalletActivity


def clamp(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("100")) -> Decimal:
    return max(low, min(high, value))


class WalletReputationEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recalculate_all(self) -> int:
        wallets = list((await self.session.scalars(select(TrackedWallet).where(TrackedWallet.status == "active"))).all())
        for wallet in wallets:
            wallet.reputation_score = await self.score_wallet(wallet.id)
        await self.session.commit()
        return len(wallets)

    async def score_wallet(self, wallet_id: int) -> Decimal:
        total, token_count, usd_total = (
            await self.session.execute(
                select(
                    func.count(WalletActivity.id),
                    func.count(func.distinct(WalletActivity.token_address)),
                    func.coalesce(func.sum(WalletActivity.usd_value), 0),
                ).where(WalletActivity.wallet_id == wallet_id)
            )
        ).one()
        total_decimal = Decimal(str(total or 0))
        token_decimal = Decimal(str(token_count or 0))
        usd_decimal = Decimal(str(usd_total or 0))
        historical_accuracy = clamp(total_decimal * Decimal("8"))
        average_return = clamp(usd_decimal / Decimal("1000"))
        early_discovery = clamp(token_decimal * Decimal("15"))
        holding_quality = clamp(token_decimal * Decimal("10"))
        holding_consistency = clamp(total_decimal * Decimal("6"))
        risk_management = Decimal("85") if total else Decimal("0")
        return clamp(
            historical_accuracy * Decimal("0.30")
            + average_return * Decimal("0.20")
            + early_discovery * Decimal("0.20")
            + holding_quality * Decimal("0.10")
            + holding_consistency * Decimal("0.10")
            + risk_management * Decimal("0.10")
        )

