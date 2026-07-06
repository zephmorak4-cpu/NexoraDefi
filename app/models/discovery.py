from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class CandidateWallet(Base):
    __tablename__ = "candidate_wallets"
    __table_args__ = (
        UniqueConstraint("chain", "wallet_address", name="uq_candidate_wallet_chain_address"),
        Index("ix_candidate_wallets_status_score", "status", "candidate_score"),
        Index("ix_candidate_wallets_type_status", "wallet_type", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String(128))
    chain: Mapped[str] = mapped_column(String(32), default="solana")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    discovery_reason: Mapped[str] = mapped_column(String(255))
    wallet_type: Mapped[str] = mapped_column(String(64), default="Unknown")
    candidate_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    reputation_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    historical_accuracy_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    suspicious_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    status: Mapped[str] = mapped_column(String(32), default="observing")
    pipeline_stage: Mapped[str] = mapped_column(String(48), default="DISCOVERED")
    pipeline_status: Mapped[str] = mapped_column(String(64), default="PENDING")
    pipeline_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    history: Mapped[list["CandidateHistory"]] = relationship(back_populates="wallet")


class CandidateHistory(Base):
    __tablename__ = "candidate_history"
    __table_args__ = (
        Index("ix_candidate_history_wallet_timestamp", "wallet_id", "timestamp"),
        Index("ix_candidate_history_token_timestamp", "token", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("candidate_wallets.id", ondelete="CASCADE"))
    signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    usd_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    dex: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fees: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    wallet: Mapped[CandidateWallet] = relationship(back_populates="history")


class CandidatePortfolioSnapshot(Base):
    __tablename__ = "candidate_portfolio_snapshots"
    __table_args__ = (Index("ix_candidate_portfolio_wallet_created", "wallet_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("candidate_wallets.id", ondelete="CASCADE"))
    total_value_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    largest_position_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    largest_position_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    top_10_holdings: Mapped[str | None] = mapped_column(Text, nullable=True)
    stablecoin_allocation: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    portfolio_concentration: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    zero_assets_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateTokenHistory(Base):
    __tablename__ = "candidate_token_history"
    __table_args__ = (
        UniqueConstraint("wallet_id", "token", name="uq_candidate_token_history_wallet_token"),
        Index("ix_candidate_token_history_wallet", "wallet_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("candidate_wallets.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(128))
    purchase_count: Mapped[int] = mapped_column(default=0)
    sale_count: Mapped[int] = mapped_column(default=0)
    average_entry_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 8), nullable=True)
    average_exit_usd: Mapped[Decimal | None] = mapped_column(Numeric(38, 8), nullable=True)
    holding_duration_days: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    roi: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    current_status: Mapped[str] = mapped_column(String(32), default="open")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
