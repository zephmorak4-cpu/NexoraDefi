from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TrackedWallet


class TrackedWalletManager:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_wallet(
        self,
        wallet_address: str,
        wallet_name: str | None = None,
        wallet_label: str | None = None,
        wallet_category: str | None = None,
        chain: str = "solana",
        source: str = "manual",
        status: str = "active",
        notes: str | None = None,
    ) -> TrackedWallet:
        address = wallet_address.strip()
        wallet = await self.session.scalar(
            select(TrackedWallet).where(
                TrackedWallet.chain == chain,
                TrackedWallet.wallet_address == address,
            )
        )
        if wallet is None:
            wallet = TrackedWallet(wallet_address=address, chain=chain)
            self.session.add(wallet)
            await self.session.flush()
        wallet.wallet_name = wallet_name
        wallet.wallet_label = wallet_label
        wallet.wallet_category = wallet_category
        wallet.source = source
        wallet.status = status
        wallet.notes = notes
        await self.session.commit()
        return wallet

    async def remove_wallet(self, wallet_address: str, chain: str = "solana") -> bool:
        wallet = await self.session.scalar(
            select(TrackedWallet).where(
                TrackedWallet.chain == chain,
                TrackedWallet.wallet_address == wallet_address,
            )
        )
        if wallet is None:
            return False
        wallet.status = "removed"
        await self.session.commit()
        return True

    async def active_wallets(self, chain: str = "solana") -> list[TrackedWallet]:
        return list(
            (
                await self.session.scalars(
                    select(TrackedWallet)
                    .where(TrackedWallet.chain == chain, TrackedWallet.status == "active")
                    .order_by(TrackedWallet.reputation_score.desc(), TrackedWallet.id)
                )
            ).all()
        )

