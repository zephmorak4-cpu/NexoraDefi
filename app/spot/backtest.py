from __future__ import annotations

from dataclasses import dataclass

from app.spot.strategy import TrendAlignedVolatilityExpansion
from app.spot.types import Candle, SignalDecision, StrategyConfig, TokenAsset


@dataclass(frozen=True)
class BacktestResult:
    total_setups_evaluated: int
    qualified_trades: int
    completed_trades: int
    win_rate: float
    average_r: float
    expectancy: float
    profit_factor: float
    max_drawdown: float


class BacktestEngine:
    def __init__(self, strategy: TrendAlignedVolatilityExpansion | None = None) -> None:
        self.strategy = strategy or TrendAlignedVolatilityExpansion()

    def run_fixture(self, token: TokenAsset, candles_4h: list[Candle], candles_1h: list[Candle], candles_15m: list[Candle], config: StrategyConfig) -> BacktestResult:
        result = self.strategy.evaluate(token, candles_4h, candles_1h, candles_15m, config)
        qualified = 1 if result.decision == SignalDecision.QUALIFIED else 0
        simulated_r = result.plan.reward_risk if result.plan else 0
        wins = 1 if simulated_r > 0 else 0
        return BacktestResult(
            total_setups_evaluated=1,
            qualified_trades=qualified,
            completed_trades=qualified,
            win_rate=100.0 if wins else 0.0,
            average_r=simulated_r,
            expectancy=simulated_r if qualified else 0.0,
            profit_factor=simulated_r if qualified else 0.0,
            max_drawdown=0.0,
        )

