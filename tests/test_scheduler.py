from app.core.config import Settings
from app.jobs.scheduler import build_scheduler


def test_scheduler_jobs_use_configured_intervals():
    settings = Settings(
        blockchain_refresh_seconds=11, market_refresh_seconds=22,
        social_refresh_seconds=33, news_refresh_seconds=44,
        wallet_analysis_interval_seconds=55, wallet_scoring_interval_seconds=66,
        wallet_discovery_interval_seconds=67,
        smart_money_signal_interval_seconds=77,
        token_rapid_change_interval_seconds=88, token_growth_interval_seconds=99,
        token_momentum_interval_seconds=111,
        risk_volatility_interval_seconds=133, risk_score_interval_seconds=144,
        risk_event_interval_seconds=155,
        analyst_report_interval_seconds=277,
        telegram_alert_interval_seconds=288,
        telegram_daily_summary_interval_seconds=299,
    )
    scheduler = build_scheduler(settings)
    jobs = {job.id: int(job.trigger.interval.total_seconds()) for job in scheduler.get_jobs()}
    assert jobs == {
        "blockchain": 11, "market": 22, "social": 33, "news": 44,
        "wallet_analysis": 55, "wallet_scoring": 66, "wallet_discovery": 67,
        "smart_money_signals": 77,
        "token_rapid_changes": 88, "token_growth": 99,
        "token_momentum": 111,
        "risk_volatility": 133, "risk_scores": 144, "risk_events": 155,
        "analyst_reports": 277,
        "telegram_smart_money_alerts": 288, "telegram_daily_summary": 299,
    }
