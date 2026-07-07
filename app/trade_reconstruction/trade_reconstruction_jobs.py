from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.trade_reconstruction.trade_reconstruction import TradeReconstructionEngine

logger = get_logger(__name__)


async def rebuild_wallet_positions() -> int:
    async with SessionFactory() as session:
        try:
            return await TradeReconstructionEngine(session).rebuild_all()
        except Exception:
            await session.rollback()
            logger.exception("wallet_position_reconstruction_failed")
            raise
