from app.core.config import get_settings
from app.database.session import SessionFactory
from app.spot.engine import SpotMomentumEngine
from app.spot.job_state import guarded_job
from app.spot.providers import ProviderCapabilityService


async def build_universe_job() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        async def work() -> dict[str, object]:
            engine = SpotMomentumEngine(settings)
            try:
                return await engine.build_universe(session)
            finally:
                await engine.close()

        return await guarded_job(session, "BUILD_UNIVERSE", work, window_minutes=1440, lock_ttl_seconds=1800)


async def refresh_market_data_job() -> dict[str, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        async def work() -> dict[str, int]:
            engine = SpotMomentumEngine(settings)
            try:
                return await engine.refresh_market_data(session)
            finally:
                await engine.close()

        return await guarded_job(session, "REFRESH_MARKET_DATA", work, window_minutes=15, lock_ttl_seconds=900)


async def scan_setups_job() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        async def work() -> dict[str, object]:
            engine = SpotMomentumEngine(settings)
            try:
                return await engine.scan_once(session)
            finally:
                await engine.close()

        return await guarded_job(session, "SCAN_SETUPS", work, window_minutes=15, lock_ttl_seconds=900)


async def provider_health_job() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        async def work() -> dict[str, object]:
            audit = await ProviderCapabilityService(settings).audit(session=session, live=True)
            return {"state": audit.state.value, "missing_capabilities": audit.missing_capabilities}

        return await guarded_job(session, "CHECK_PROVIDERS", work, window_minutes=15, lock_ttl_seconds=600)


async def monitor_paper_trades_job() -> dict[str, int]:
    async with SessionFactory() as session:
        async def work() -> dict[str, int]:
            return {"monitored": 0, "updates": 0}

        return await guarded_job(session, "MONITOR_PAPER_POSITIONS", work, window_minutes=5, lock_ttl_seconds=300)


async def daily_performance_job() -> dict[str, int]:
    async with SessionFactory() as session:
        async def work() -> dict[str, int]:
            return {"completed_trades": 0, "digest_sent": 0}

        return await guarded_job(session, "SEND_DAILY_REPORT", work, window_minutes=1440, lock_ttl_seconds=900)
