from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TokenTxns:
    buys: int = 0
    sells: int = 0


@dataclass(frozen=True)
class ProviderCallResult:
    ok: bool
    provider: str
    data: Any = None
    error: str | None = None


@dataclass(frozen=True)
class ProviderSnapshot:
    provider: str
    raw_response: dict[str, Any] | list[Any] | None
    normalized_data: dict[str, Any]


@dataclass(frozen=True)
class TokenLaunch:
    token_address: str
    pair_address: str | None = None
    symbol: str | None = None
    name: str | None = None
    creator_wallet: str | None = None
    launch_time: str | None = None
    dex: str | None = None
    source: str = "unknown"
    liquidity_usd: float | None = None
    market_cap_usd: float | None = None
    fdv_usd: float | None = None
    price_usd: float | None = None
    volume_usd: float | None = None
    volume_usd_24h: float | None = None
    volume_usd_1h: float | None = None
    volume_usd_5m: float | None = None
    txns: TokenTxns = field(default_factory=TokenTxns)
    txns_1h: TokenTxns = field(default_factory=TokenTxns)
    txns_5m: TokenTxns = field(default_factory=TokenTxns)
    holder_count: int | None = None
    top10_holder_percent: float | None = None
    creator_hold_percent: float | None = None
    liquidity_drop_percent: float | None = None
    mint_authority: str | None = None
    freeze_authority: str | None = None
    mint_authority_active: bool | None = None
    freeze_authority_active: bool | None = None
    is_mutable: bool | None = None
    risk_flags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    provider_snapshots: list[ProviderSnapshot] = field(default_factory=list)


@dataclass(frozen=True)
class AgentScore:
    score: float
    passed: bool
    reasons: list[str]


@dataclass(frozen=True)
class RiskScore(AgentScore):
    risk_level: str = "MEDIUM"


@dataclass(frozen=True)
class SmartMoneyScore(AgentScore):
    smart_wallets_detected: int = 0


@dataclass(frozen=True)
class DecisionResult:
    final_score: float
    decision: str
    should_alert: bool
    summary: str
    reasons: list[str]
