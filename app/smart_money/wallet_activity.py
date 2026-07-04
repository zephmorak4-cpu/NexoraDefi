from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WalletActivity
from app.smart_money.provider import WalletTransfer


class WalletActivityRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_transfer(self, wallet_id: int, transfer: WalletTransfer) -> bool:
        exists = await self.session.scalar(
            select(WalletActivity.id).where(
                WalletActivity.wallet_id == wallet_id,
                WalletActivity.transaction_signature == transfer.signature,
                WalletActivity.token_address == transfer.token_address,
            )
        )
        if exists:
            return False
        self.session.add(
            WalletActivity(
                wallet_id=wallet_id,
                token_address=transfer.token_address,
                token_symbol=transfer.token_symbol,
                transaction_signature=transfer.signature,
                transaction_type=transfer.transaction_type,
                amount=transfer.amount,
                usd_value=transfer.usd_value if transfer.usd_value is not None else Decimal("0"),
                timestamp=transfer.timestamp,
            )
        )
        return True

