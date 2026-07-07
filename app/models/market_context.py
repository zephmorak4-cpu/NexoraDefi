from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.smart_money import WalletPosition


class MarketContext(Base):
    __tablename__ = "market_context"
    __table_args__ = (
        UniqueConstraint("wallet_position_id", name="uq_market_context_wallet_position"),
        Index("ix_market_context_token_entry", "token_address", "entry_timestamp"),
        Index("ix_market_context_score", "context_score", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_position_id: Mapped[int] = mapped_column(ForeignKey("wallet_positions.id", ondelete="CASCADE"), index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    entry_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market_cap_entry: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    market_cap_exit: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    liquidity_entry: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    liquidity_exit: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    holder_count_entry: Mapped[int | None] = mapped_column(nullable=True)
    holder_count_exit: Mapped[int | None] = mapped_column(nullable=True)
    daily_volume_entry: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    daily_volume_exit: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    token_age_entry: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    token_age_exit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_entry: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    price_exit: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    market_sentiment: Mapped[str] = mapped_column(String(64), default="Insufficient Market Data")
    wallet_consensus: Mapped[str] = mapped_column(String(255), default="Insufficient Market Data")
    context_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    position: Mapped[WalletPosition] = relationship()
