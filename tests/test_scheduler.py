from app.core.config import Settings
from app.jobs.scheduler import build_scheduler


def test_scheduler_registers_spot_paper_workflows():
    settings = Settings()
    scheduler = build_scheduler(settings)

    assert {job.id for job in scheduler.get_jobs()} == {
        "spot_build_universe",
        "spot_refresh_market_data",
        "spot_scan_setups",
        "spot_monitor_paper_trades",
        "spot_provider_health",
        "spot_daily_performance",
    }
