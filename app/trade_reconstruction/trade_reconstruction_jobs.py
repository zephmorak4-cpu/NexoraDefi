from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.trade_reconstruction.trade_reconstruction import TradeReconstructionEngine
from app.trade_reconstruction.cost_basis import CostBasisEnrichmentEngine
from app.core.config import get_settings

logger = get_logger(__name__)


async def rebuild_wallet_positions() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        enrichment = CostBasisEnrichmentEngine(session, settings)
        try:
            await enrichment.enrich_missing_history()
            return await TradeReconstructionEngine(session).rebuild_all()
        except Exception:
            await session.rollback()
            logger.exception("wallet_position_reconstruction_failed")
            raise
        finally:
            await enrichment.close()
