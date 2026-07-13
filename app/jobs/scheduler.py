from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings
from app.spot.jobs import (
    build_universe_job,
    daily_performance_job,
    monitor_paper_trades_job,
    provider_health_job,
    refresh_market_data_job,
    scan_setups_job,
)


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    if not settings.paper_trading_enabled or settings.live_trading_enabled:
        return scheduler
    jobs = (
        (build_universe_job, "spot_build_universe", 24 * 60 * 60),
        (refresh_market_data_job, "spot_refresh_market_data", settings.market_scan_interval_minutes * 60),
        (scan_setups_job, "spot_scan_setups", settings.market_scan_interval_minutes * 60),
        (monitor_paper_trades_job, "spot_monitor_paper_trades", settings.position_monitor_interval_minutes * 60),
        (provider_health_job, "spot_provider_health", settings.provider_health_interval_minutes * 60),
        (daily_performance_job, "spot_daily_performance", settings.daily_performance_interval_hours * 3600),
    )
    for task, job_id, seconds in jobs:
        scheduler.add_job(
            task,
            "interval",
            seconds=seconds,
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=max(seconds, 30),
        )
    return scheduler
