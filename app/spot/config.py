from __future__ import annotations

from app.core.config import Settings
from app.spot.types import StrategyConfig


def strategy_config_from_settings(settings: Settings) -> StrategyConfig:
    return StrategyConfig(
        version=settings.strategy_version,
        ema_fast=settings.strategy_ema_fast,
        ema_slow=settings.strategy_ema_slow,
        atr_period=settings.strategy_atr_period,
        min_reward_risk=settings.signal_min_reward_risk,
        min_quality_score=settings.signal_min_quality_score,
        max_stop_distance_percent=settings.max_stop_distance_percent,
        min_stop_distance_percent=settings.min_stop_distance_percent,
    )

