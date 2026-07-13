from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class ReadinessState(StrEnum):
    NOT_READY = "NOT_READY"
    DEGRADED = "DEGRADED"
    READY_FOR_BACKTESTING = "READY_FOR_BACKTESTING"
    READY_FOR_PAPER_OBSERVATION = "READY_FOR_PAPER_OBSERVATION"


class ProviderStatus(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CHECKING = "CHECKING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_FAILED = "AUTH_FAILED"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    OFFLINE = "OFFLINE"


class Regime(StrEnum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"


class SignalDecision(StrEnum):
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


class PaperTradeState(StrEnum):
    SIGNALLED = "SIGNALLED"
    WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
    OPEN = "OPEN"
    PARTIALLY_EXITED = "PARTIALLY_EXITED"
    CLOSED_TP = "CLOSED_TP"
    CLOSED_SL = "CLOSED_SL"
    CLOSED_TRAILING = "CLOSED_TRAILING"
    CLOSED_TIME = "CLOSED_TIME"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class TokenAsset:
    chain: str
    address: str
    symbol: str
    name: str
    decimals: int | None = None
    created_at: datetime | None = None
    market_cap_usd: float | None = None
    fdv_usd: float | None = None
    liquidity_usd: float | None = None
    volume_24h_usd: float | None = None
    primary_pool_address: str | None = None
    primary_dex: str | None = None
    quote_asset: str | None = None
    data_sources: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Candle:
    token_address: str
    pool_address: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    is_closed: bool = True


@dataclass(frozen=True)
class MarketQuote:
    token_address: str
    price_usd: float
    liquidity_usd: float | None
    timestamp: datetime
    source: str
    stale: bool = False


@dataclass(frozen=True)
class StrategyConfig:
    version: str = "spot-momentum-v1"
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    consolidation_lookback: int = 20
    breakout_lookback: int = 20
    volume_lookback: int = 20
    volume_multiplier: float = 1.5
    max_consolidation_atr: float = 3.0
    stop_atr_buffer: float = 1.2
    min_reward_risk: float = 2.0
    min_quality_score: float = 80.0
    max_stop_distance_percent: float = 6.0
    min_stop_distance_percent: float = 0.8
    entry_zone_atr_fraction: float = 0.25
    target_rr: tuple[float, float, float] = (1.1, 2.1, 3.5)


@dataclass(frozen=True)
class TradePlan:
    token: TokenAsset
    strategy_version: str
    quality_score: float
    regime: Regime
    entry_low: float
    entry_high: float
    reference_entry: float
    stop_loss: float
    targets: tuple[float, float, float]
    reward_risk: float
    expectancy_r: float
    fingerprint: str
    reasons: list[str]
    risks: list[str]


@dataclass(frozen=True)
class SetupEvaluationResult:
    decision: SignalDecision
    token: TokenAsset
    quality_score: float
    reward_risk: float | None
    reasons: list[str]
    plan: TradePlan | None = None

