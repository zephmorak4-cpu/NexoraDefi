from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.smart_money.provider import BlockchainProvider
from app.smart_money.wallet_monitor import WalletMonitor


class BlockchainCollector:
    """Compatibility wrapper for the Solana-first wallet monitor."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: BlockchainProvider | None = None,
        **_: object,
    ) -> None:
        self.monitor = WalletMonitor(session, settings, provider=provider)

    async def collect(self) -> int:
        return await self.monitor.monitor()

    async def close(self) -> None:
        await self.monitor.close()
