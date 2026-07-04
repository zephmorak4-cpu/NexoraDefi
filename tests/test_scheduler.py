from app.core.config import Settings
from app.jobs.scheduler import build_scheduler


def test_scheduler_jobs_use_configured_intervals():
    settings = Settings(
        blockchain_refresh_seconds=11, market_refresh_seconds=22,
        social_refresh_seconds=33, news_refresh_seconds=44,
        wallet_analysis_interval_seconds=55, wallet_scoring_interval_seconds=66,
        wallet_monitor_interval_seconds=67,
        wallet_reputation_interval_seconds=68,
        token_quality_interval_seconds=69,
        candidate_discovery_interval_seconds=70,
        candidate_scoring_interval_seconds=71,
        candidate_promotion_interval_seconds=72,
        elite_demotion_interval_seconds=73,
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
        "wallet_analysis": 55, "wallet_scoring": 66,
        "candidate_wallet_discovery": 70, "candidate_wallet_scoring": 71,
        "candidate_wallet_promotions": 72, "elite_wallet_demotions": 73,
        "solana_wallet_monitor": 67, "solana_wallet_reputation": 68, "solana_token_quality": 69,
        "solana_smart_money_signals": 77, "legacy_smart_money_signals": 77,
        "token_rapid_changes": 88, "token_growth": 99,
        "token_momentum": 111,
        "risk_volatility": 133, "risk_scores": 144, "risk_events": 155,
        "analyst_reports": 277,
        "telegram_smart_money_alerts": 288, "telegram_daily_summary": 299,
    }
