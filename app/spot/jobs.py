from app.core.config import get_settings
from app.database.session import SessionFactory
from app.spot.engine import SpotMomentumEngine
from app.spot.providers import ProviderCapabilityService


async def build_universe_job() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = SpotMomentumEngine(settings)
        try:
            return await engine.build_universe(session)
        finally:
            await engine.close()


async def refresh_market_data_job() -> dict[str, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = SpotMomentumEngine(settings)
        try:
            return await engine.refresh_market_data(session)
        finally:
            await engine.close()


async def scan_setups_job() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = SpotMomentumEngine(settings)
        try:
            return await engine.scan_once(session)
        finally:
            await engine.close()


async def provider_health_job() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        audit = await ProviderCapabilityService(settings).audit(session=session, live=True)
        return {"state": audit.state.value, "missing_capabilities": audit.missing_capabilities}


async def monitor_paper_trades_job() -> dict[str, int]:
    return {"monitored": 0, "updates": 0}


async def daily_performance_job() -> dict[str, int]:
    return {"completed_trades": 0, "digest_sent": 0}
