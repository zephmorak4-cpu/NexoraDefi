from sqlalchemy import select

from app.analyst.analyst_engine import AnalystEngine
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.models import SmartMoneySignal

logger = get_logger(__name__)


async def generate_analyst_reports() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            token_ids = (
                await session.scalars(
                    select(SmartMoneySignal.token_id)
                    .distinct()
                    .order_by(SmartMoneySignal.token_id)
                    .limit(settings.analyst_batch_size)
                )
            ).all()
            engine = AnalystEngine(session, settings)
            for token_id in token_ids:
                await engine.token_report(token_id)
            logger.info("analyst_reports_generated", reports=len(token_ids))
            return len(token_ids)
        except Exception:
            await session.rollback()
            logger.exception("analyst_report_generation_failed")
            raise


async def generate_report_after_smart_money_signal(token_id: int) -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        await AnalystEngine(session, settings).token_report(token_id)
        return 1
