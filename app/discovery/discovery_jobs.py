from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.discovery.candidate_scoring import CandidateScoringEngine
from app.discovery.discovery_engine import DiscoveryEngine
from app.discovery.wallet_promotion import WalletPromotionService

logger = get_logger(__name__)


async def discover_candidate_wallets() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = DiscoveryEngine(session, settings)
        try:
            return await engine.discover()
        except Exception:
            await session.rollback()
            logger.exception("candidate_wallet_discovery_failed")
            raise
        finally:
            await engine.close()


async def update_candidate_scores() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await CandidateScoringEngine(session, settings).score_all()
        except Exception:
            await session.rollback()
            logger.exception("candidate_wallet_scoring_failed")
            raise


async def evaluate_elite_demotions() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await WalletPromotionService(session, settings).evaluate_demotions()
        except Exception:
            await session.rollback()
            logger.exception("elite_wallet_demotion_failed")
            raise
