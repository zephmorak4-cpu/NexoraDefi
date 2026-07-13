from __future__ import annotations

from app.spot.types import Candle


def ema(values: list[float], period: int) -> list[float]:
    if period < 1:
        raise ValueError("period must be positive")
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [float(values[0])]
    for value in values[1:]:
        result.append((float(value) * alpha) + (result[-1] * (1 - alpha)))
    return result


def true_ranges(candles: list[Candle]) -> list[float]:
    ranges: list[float] = []
    previous_close: float | None = None
    for candle in candles:
        if previous_close is None:
            ranges.append(candle.high - candle.low)
        else:
            ranges.append(
                max(
                    candle.high - candle.low,
                    abs(candle.high - previous_close),
                    abs(candle.low - previous_close),
                )
            )
        previous_close = candle.close
    return ranges


def atr(candles: list[Candle], period: int = 14) -> list[float]:
    ranges = true_ranges(candles)
    if not ranges:
        return []
    return ema(ranges, period)


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def swing_high(candles: list[Candle], lookback: int) -> float | None:
    window = candles[-lookback:]
    return max((candle.high for candle in window), default=None)


def swing_low(candles: list[Candle], lookback: int) -> float | None:
    window = candles[-lookback:]
    return min((candle.low for candle in window), default=None)


def validate_closed_candles(candles: list[Candle]) -> list[str]:
    reasons: list[str] = []
    if not candles:
        return ["missing candle history"]
    timestamps = set()
    for candle in candles:
        if not candle.is_closed:
            reasons.append("contains incomplete candle")
        if min(candle.open, candle.close) < candle.low or max(candle.open, candle.close) > candle.high:
            reasons.append("malformed OHLC relationship")
        if candle.close <= 0 or candle.open <= 0 or candle.high <= 0 or candle.low <= 0:
            reasons.append("zero or negative candle price")
        if candle.timestamp in timestamps:
            reasons.append("duplicate candle timestamp")
        timestamps.add(candle.timestamp)
    return sorted(set(reasons))

