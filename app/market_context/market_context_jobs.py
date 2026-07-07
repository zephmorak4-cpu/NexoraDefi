from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.market_context.market_context import MarketContextEngine

logger = get_logger(__name__)


async def enrich_market_context() -> dict[str, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        enriched = await MarketContextEngine(session, settings).enrich_all_positions()
    logger.info("market_context_enriched", positions=enriched)
    return {"positions": enriched}
