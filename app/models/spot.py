from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ProviderHealthRecord(Base):
    __tablename__ = "spot_provider_health"
    __table_args__ = (UniqueConstraint("provider", "capability", name="uq_spot_provider_capability"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    capability: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SpotToken(Base):
    __tablename__ = "spot_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    chain: Mapped[str] = mapped_column(String(32), default="solana", index=True)
    address: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    decimals: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market_cap_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    fdv_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    liquidity_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    volume_24h_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    primary_pool_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    primary_dex: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quote_asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_sources: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SpotTokenPool(Base):
    __tablename__ = "spot_token_pools"
    __table_args__ = (UniqueConstraint("token_address", "pool_address", name="uq_spot_token_pool"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    pool_address: Mapped[str] = mapped_column(String(128), index=True)
    dex: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quote_asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    liquidity_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    volume_24h_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SpotUniverseSnapshot(Base):
    __tablename__ = "spot_universe_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="BUILT")
    candidates_discovered: Mapped[int] = mapped_column(default=0)
    eligible_count: Mapped[int] = mapped_column(default=0)
    core_count: Mapped[int] = mapped_column(default=0)
    candidate_count: Mapped[int] = mapped_column(default=0)
    excluded_count: Mapped[int] = mapped_column(default=0)
    exclusion_summary: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpotUniverseMember(Base):
    __tablename__ = "spot_universe_members"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "token_address", name="uq_spot_universe_member"),
        Index("ix_spot_universe_tier_rank", "tier", "rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), ForeignKey("spot_universe_snapshots.snapshot_id"), index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    tier: Mapped[str] = mapped_column(String(32), index=True)
    rank: Mapped[int | None] = mapped_column(nullable=True)
    score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    factors: Mapped[dict] = mapped_column(JSON, default=dict)


class SpotCandle(Base):
    __tablename__ = "spot_candles"
    __table_args__ = (
        UniqueConstraint("token_address", "pool_address", "timeframe", "timestamp", "source", name="uq_spot_candle"),
        Index("ix_spot_candle_token_timeframe_timestamp", "token_address", "timeframe", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    pool_address: Mapped[str] = mapped_column(String(128), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    high: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    low: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    close: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    volume: Mapped[Decimal] = mapped_column(Numeric(38, 8), default=0)
    source: Mapped[str] = mapped_column(String(64))
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True)


class SpotSetupEvaluation(Base):
    __tablename__ = "spot_setup_evaluations"
    __table_args__ = (Index("ix_spot_setup_scan_token", "scan_id", "token_address"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str] = mapped_column(String(64), index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    strategy_version: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32), index=True)
    quality_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    reward_risk: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    rejection_reasons: Mapped[list] = mapped_column(JSON, default=list)
    plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpotTradeSignal(Base):
    __tablename__ = "spot_trade_signals"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_spot_signal_fingerprint"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    strategy_version: Mapped[str] = mapped_column(String(64))
    quality_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    reward_risk: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    plan_json: Mapped[dict] = mapped_column(JSON)
    notification_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperAccount(Base):
    __tablename__ = "spot_paper_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, default="default")
    starting_balance_usd: Mapped[Decimal] = mapped_column(Numeric(38, 2))
    cash_balance_usd: Mapped[Decimal] = mapped_column(Numeric(38, 2))
    equity_usd: Mapped[Decimal] = mapped_column(Numeric(38, 2))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaperPosition(Base):
    __tablename__ = "spot_paper_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 12), nullable=True)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    target_1: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    target_2: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    target_3: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(38, 12), nullable=True)
    realized_pnl_usd: Mapped[Decimal] = mapped_column(Numeric(38, 2), default=0)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperFill(Base):
    __tablename__ = "spot_paper_fills"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("spot_paper_positions.id"), index=True)
    fill_type: Mapped[str] = mapped_column(String(32))
    price: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    fee_usd: Mapped[Decimal] = mapped_column(Numeric(38, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyPerformance(Base):
    __tablename__ = "spot_daily_performance"
    __table_args__ = (UniqueConstraint("date", name="uq_spot_daily_performance_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    metrics_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
