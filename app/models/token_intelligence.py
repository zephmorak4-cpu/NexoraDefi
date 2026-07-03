from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.entities import Token


class TokenGrowthMetric(Base):
    __tablename__ = "token_growth_metrics"
    __table_args__ = (
        UniqueConstraint("token_id", "calculated_at", name="uq_token_growth_calculated"),
        Index("ix_token_growth_token_calculated", "token_id", "calculated_at"),
        Index("ix_token_growth_calculated", "calculated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    holder_count: Mapped[int] = mapped_column(Integer, default=0)
    holder_growth_24h: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    holder_growth_7d: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)
    transaction_growth_24h: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    transaction_growth_7d: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    volume_24h: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    volume_growth_24h: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    volume_growth_7d: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    market_cap_growth_24h: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    market_cap_growth_7d: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    liquidity_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    liquidity_growth_24h: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    liquidity_growth_7d: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    token: Mapped[Token] = relationship()


class MomentumMetric(Base):
    __tablename__ = "momentum_metrics"
    __table_args__ = (
        UniqueConstraint("token_id", "calculated_at", name="uq_momentum_calculated"),
        Index("ix_momentum_token_calculated", "token_id", "calculated_at"),
        Index("ix_momentum_rank", "momentum_score", "calculated_at"),
        CheckConstraint("volatility_score >= 0 AND volatility_score <= 100", name="ck_momentum_volatility"),
        CheckConstraint("momentum_score >= 0 AND momentum_score <= 100", name="ck_momentum_score"),
        CheckConstraint(
            "momentum_stage IN ('EARLY', 'ACCELERATING', 'TRENDING', 'OVERHEATED', 'DECLINING')",
            name="ck_momentum_stage",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    price_change_1h: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    price_change_24h: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    price_change_7d: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    price_change_30d: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    volatility_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    momentum_score: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    momentum_stage: Mapped[str] = mapped_column(String(32))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    token: Mapped[Token] = relationship()

