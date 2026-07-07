from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AlphaScannedToken(Base):
    __tablename__ = "alpha_scanned_tokens"
    __table_args__ = (
        UniqueConstraint("token_address", "pair_address", name="uq_alpha_scanned_token_pair"),
        Index("ix_alpha_scanned_tokens_decision", "decision", "last_seen_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    pair_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    creator_wallet: Mapped[str | None] = mapped_column(String(128), nullable=True)
    launch_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dex: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    liquidity_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    market_cap_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 12), nullable=True)
    volume_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    buys: Mapped[int] = mapped_column(default=0)
    sells: Mapped[int] = mapped_column(default=0)
    final_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    decision: Mapped[str] = mapped_column(String(32), default="IGNORE")
    should_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reasons: Mapped[list] = mapped_column(JSON, default=list)
    agent_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AlphaAlertHistory(Base):
    __tablename__ = "alpha_alert_history"
    __table_args__ = (Index("ix_alpha_alert_token_created", "token_address", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    final_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlphaWatchlistToken(Base):
    __tablename__ = "alpha_watchlist_tokens"
    __table_args__ = (UniqueConstraint("token_address", name="uq_alpha_watchlist_token"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    final_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlphaSmartWallet(Base):
    __tablename__ = "alpha_smart_wallets"
    __table_args__ = (UniqueConstraint("address", name="uq_alpha_smart_wallet_address"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=50)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AlphaProviderSnapshot(Base):
    __tablename__ = "alpha_provider_snapshots"
    __table_args__ = (Index("ix_alpha_provider_snapshot_token_created", "token_address", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    pair_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    raw_response_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    normalized_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
