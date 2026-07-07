from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.trade_reconstruction.cost_basis import CostBasisEnrichmentEngine

logger = get_logger(__name__)


async def enrich_candidate_cost_basis() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = CostBasisEnrichmentEngine(session, settings)
        try:
            return await engine.enrich_missing_history()
        except Exception:
            await session.rollback()
            logger.exception("candidate_cost_basis_enrichment_failed")
            raise
        finally:
            await engine.close()
