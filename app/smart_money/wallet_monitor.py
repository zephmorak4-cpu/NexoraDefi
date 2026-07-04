from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.smart_money.provider import BlockchainProvider, SolanaProvider
from app.smart_money.tracked_wallets import TrackedWalletManager
from app.smart_money.wallet_activity import WalletActivityRecorder

logger = get_logger(__name__)


class WalletMonitor:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: BlockchainProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider or SolanaProvider(settings)
        self.wallets = TrackedWalletManager(session)
        self.activity = WalletActivityRecorder(session)

    async def monitor(self) -> int:
        active_wallets = await self.wallets.active_wallets(chain=self.provider.chain)
        stored = 0
        for wallet in active_wallets:
            transfers = await self.provider.wallet_transfers(
                wallet.wallet_address,
                limit=self.settings.wallet_monitor_transfer_limit,
            )
            for transfer in transfers:
                stored += int(await self.activity.record_transfer(wallet.id, transfer))
        await self.session.commit()
        logger.info("solana_wallet_monitor_complete", wallets=len(active_wallets), activities=stored)
        return stored

    async def close(self) -> None:
        await self.provider.close()

