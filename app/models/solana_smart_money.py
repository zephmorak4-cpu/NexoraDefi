from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TrackedWallet(Base):
    __tablename__ = "tracked_wallets"
    __table_args__ = (
        UniqueConstraint("chain", "wallet_address", name="uq_tracked_wallet_chain_address"),
        Index("ix_tracked_wallets_chain_status", "chain", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String(128))
    wallet_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wallet_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wallet_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chain: Mapped[str] = mapped_column(String(32), default="solana")
    source: Mapped[str] = mapped_column(String(64), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reputation_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    activities: Mapped[list["WalletActivity"]] = relationship(back_populates="wallet")


class WalletActivity(Base):
    __tablename__ = "wallet_activity"
    __table_args__ = (
        UniqueConstraint("wallet_id", "transaction_signature", "token_address", name="uq_wallet_activity_event"),
        Index("ix_wallet_activity_wallet_timestamp", "wallet_id", "timestamp"),
        Index("ix_wallet_activity_token_timestamp", "token_address", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("tracked_wallets.id", ondelete="CASCADE"))
    token_address: Mapped[str] = mapped_column(String(128))
    token_symbol: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    transaction_signature: Mapped[str] = mapped_column(String(160))
    transaction_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    usd_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    wallet: Mapped[TrackedWallet] = relationship(back_populates="activities")


class TokenQuality(Base):
    __tablename__ = "token_quality"
    __table_args__ = (
        UniqueConstraint("token_address", name="uq_token_quality_address"),
        CheckConstraint("quality_score >= 0 AND quality_score <= 100", name="ck_token_quality_score"),
        Index("ix_token_quality_score", "quality_score", "calculated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_address: Mapped[str] = mapped_column(String(128))
    token_symbol: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    quality_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    liquidity_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    volume_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    holder_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    age_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    market_cap_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
