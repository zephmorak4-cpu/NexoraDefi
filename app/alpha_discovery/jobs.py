from app.alpha_discovery.engine import SolanaAlphaDiscoveryEngine
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory

logger = get_logger(__name__)


async def scan_new_launches() -> dict[str, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = SolanaAlphaDiscoveryEngine(session, settings)
        try:
            return await engine.scan()
        except Exception:
            await session.rollback()
            logger.exception("alpha_discovery_scan_failed")
            raise
        finally:
            await engine.close()
