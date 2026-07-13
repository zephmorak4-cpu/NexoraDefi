from __future__ import annotations

from hashlib import sha256

from app.spot.indicators import atr, average, ema, swing_high, swing_low, validate_closed_candles
from app.spot.types import Candle, Regime, SetupEvaluationResult, SignalDecision, StrategyConfig, TokenAsset, TradePlan


class MarketRegimeService:
    def classify(self, candles_4h: list[Candle], config: StrategyConfig) -> Regime:
        if len(candles_4h) < max(config.ema_slow, config.atr_period) + 5:
            return Regime.DATA_INSUFFICIENT
        closes = [c.close for c in candles_4h if c.is_closed]
        fast = ema(closes, config.ema_fast)[-1]
        slow = ema(closes, config.ema_slow)[-1]
        last = closes[-1]
        if last > fast > slow:
            return Regime.BULLISH
        if last < fast < slow:
            return Regime.BEARISH
        return Regime.NEUTRAL


class TrendAlignedVolatilityExpansion:
    def evaluate(
        self,
        token: TokenAsset,
        candles_4h: list[Candle],
        candles_1h: list[Candle],
        candles_15m: list[Candle],
        config: StrategyConfig,
    ) -> SetupEvaluationResult:
        reasons: list[str] = []
        risks: list[str] = []
        for label, candles in (("4h", candles_4h), ("1h", candles_1h), ("15m", candles_15m)):
            invalid = validate_closed_candles(candles)
            reasons.extend(f"{label}: {reason}" for reason in invalid)
        if reasons:
            return self._rejected(token, reasons)

        regime = MarketRegimeService().classify(candles_4h, config)
        if regime in {Regime.BEARISH, Regime.DATA_INSUFFICIENT}:
            return self._rejected(token, [f"market regime blocks longs: {regime.value}"])

        if len(candles_1h) < config.ema_slow + 5 or len(candles_15m) < config.breakout_lookback + 2:
            return self._rejected(token, ["insufficient required candle history"])

        closes_1h = [c.close for c in candles_1h]
        fast_1h = ema(closes_1h, config.ema_fast)[-1]
        slow_1h = ema(closes_1h, config.ema_slow)[-1]
        if not (closes_1h[-1] > fast_1h > slow_1h):
            return self._rejected(token, ["1h trend is not aligned bullish"])

        atr_15m = atr(candles_15m, config.atr_period)
        latest_atr = atr_15m[-1] if atr_15m else 0.0
        if latest_atr <= 0:
            return self._rejected(token, ["ATR unavailable"])

        setup_window = candles_15m[-(config.breakout_lookback + 1):-1]
        trigger = candles_15m[-1]
        range_high = swing_high(setup_window, config.consolidation_lookback)
        range_low = swing_low(setup_window, config.consolidation_lookback)
        if range_high is None or range_low is None:
            return self._rejected(token, ["consolidation range unavailable"])
        range_width = range_high - range_low
        if range_width <= 0 or range_width > latest_atr * config.max_consolidation_atr:
            return self._rejected(token, ["valid consolidation not detected"])
        if trigger.close <= range_high:
            return self._rejected(token, ["15m candle did not close above range high"])

        baseline_volume = average([c.volume for c in setup_window[-config.volume_lookback:]])
        if baseline_volume <= 0 or trigger.volume < baseline_volume * config.volume_multiplier:
            return self._rejected(token, ["breakout volume confirmation failed"])

        entry_high = trigger.close
        entry_low = max(range_high, trigger.close - latest_atr * config.entry_zone_atr_fraction)
        reference_entry = (entry_low + entry_high) / 2
        structural_stop = range_low
        volatility_stop = reference_entry - latest_atr * config.stop_atr_buffer
        stop_loss = min(structural_stop, volatility_stop)
        stop_distance = reference_entry - stop_loss
        if stop_distance <= 0:
            return self._rejected(token, ["invalid stop distance"])
        stop_percent = stop_distance / reference_entry * 100
        if stop_percent > config.max_stop_distance_percent:
            return self._rejected(token, ["stop distance too wide"])
        if stop_percent < config.min_stop_distance_percent:
            return self._rejected(token, ["stop distance too tight"])

        targets = tuple(reference_entry + stop_distance * rr for rr in config.target_rr)
        reward_risk = (targets[1] - reference_entry) / stop_distance
        if reward_risk < config.min_reward_risk:
            return self._rejected(token, ["reward/risk below minimum"])

        quality = self._quality_score(regime, reward_risk, trigger.volume / baseline_volume, range_width / latest_atr)
        if quality < config.min_quality_score:
            return self._rejected(token, [f"quality score below minimum: {quality:.1f}"])

        if regime == Regime.NEUTRAL:
            risks.append("neutral Solana regime requires stronger follow-through")
        fingerprint = self._fingerprint(config.version, token.address, range_high, range_low, trigger.timestamp.isoformat())
        plan = TradePlan(
            token=token,
            strategy_version=config.version,
            quality_score=round(quality, 2),
            regime=regime,
            entry_low=round(entry_low, 12),
            entry_high=round(entry_high, 12),
            reference_entry=round(reference_entry, 12),
            stop_loss=round(stop_loss, 12),
            targets=tuple(round(target, 12) for target in targets),
            reward_risk=round(reward_risk, 3),
            expectancy_r=round((quality / 100 * reward_risk) - (1 - quality / 100), 3),
            fingerprint=fingerprint,
            reasons=[
                "4h and 1h trends aligned",
                "15m volatility contracted",
                "confirmed breakout on a closed candle",
                "breakout volume above baseline",
                "valid reward/risk after structural and ATR stop",
            ],
            risks=risks or ["normal volatility and execution-cost risk"],
        )
        return SetupEvaluationResult(SignalDecision.QUALIFIED, token, plan.quality_score, plan.reward_risk, [], plan)

    @staticmethod
    def _rejected(token: TokenAsset, reasons: list[str]) -> SetupEvaluationResult:
        return SetupEvaluationResult(SignalDecision.REJECTED, token, 0.0, None, sorted(set(reasons)))

    @staticmethod
    def _quality_score(regime: Regime, reward_risk: float, volume_ratio: float, range_atr: float) -> float:
        score = 50.0
        score += 12 if regime == Regime.BULLISH else 5
        score += min(15, max(0, (reward_risk - 1.5) * 8))
        score += min(15, max(0, (volume_ratio - 1) * 8))
        score += max(0, 10 - abs(range_atr - 1.5) * 4)
        return max(0, min(100, score))

    @staticmethod
    def _fingerprint(version: str, token: str, range_high: float, range_low: float, trigger_time: str) -> str:
        raw = f"{version}:{token}:{range_high:.12f}:{range_low:.12f}:{trigger_time}"
        return sha256(raw.encode("utf-8")).hexdigest()

