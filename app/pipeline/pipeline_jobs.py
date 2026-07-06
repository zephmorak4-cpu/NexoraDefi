from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.discovery.candidate_scoring import CandidateScoringEngine

logger = get_logger(__name__)


async def run_wallet_pipeline() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await CandidateScoringEngine(session, settings).score_all()
        except Exception:
            await session.rollback()
            logger.exception("wallet_pipeline_failed")
            raise
