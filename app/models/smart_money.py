from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.entities import Token, Wallet


class WalletMetric(Base):
    __tablename__ = "wallet_metrics"
    __table_args__ = (
        CheckConstraint("win_rate >= 0 AND win_rate <= 100", name="ck_wallet_metrics_win_rate"),
        CheckConstraint("loss_rate >= 0 AND loss_rate <= 100", name="ck_wallet_metrics_loss_rate"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), unique=True, index=True
    )
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    total_buys: Mapped[int] = mapped_column(Integer, default=0)
    total_sells: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_traded: Mapped[int] = mapped_column(Integer, default=0)
    last_processed_transaction_id: Mapped[int] = mapped_column(Integer, default=0)
    estimated_total_profit: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    estimated_roi_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    average_return_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    average_holding_time_days: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    loss_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    largest_winner_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    largest_loss_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    wallet: Mapped[Wallet] = relationship()


class WalletScore(Base):
    __tablename__ = "wallet_scores"
    __table_args__ = (
        Index("ix_wallet_scores_wallet_calculated", "wallet_id", "calculated_at"),
        Index("ix_wallet_scores_rank", "final_smart_money_score", "calculated_at"),
        CheckConstraint("final_smart_money_score >= 0 AND final_smart_money_score <= 100", name="ck_wallet_scores_final"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_wallet_scores_confidence"),
        CheckConstraint(
            "wallet_tier IN ('ELITE', 'ADVANCED', 'INTERMEDIATE', 'SPECULATIVE', 'LOW_QUALITY')",
            name="ck_wallet_scores_tier",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    profitability_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    consistency_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    risk_management_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    experience_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    recent_performance_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    final_smart_money_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    wallet_tier: Mapped[str] = mapped_column(String(32), index=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    wallet: Mapped[Wallet] = relationship()


class WalletPosition(Base):
    __tablename__ = "wallet_positions"
    __table_args__ = (
        UniqueConstraint("wallet_id", "token_id", name="uq_wallet_position_wallet_token"),
        Index("ix_wallet_positions_token_activity", "token_id", "latest_activity_date"),
        Index("ix_wallet_positions_wallet_activity", "wallet_id", "latest_activity_date"),
        CheckConstraint("current_balance >= 0", name="ck_wallet_positions_balance"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    total_bought_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    total_sold_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    realized_profit: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    unrealized_profit: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    first_purchase_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_activity_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    wallet: Mapped[Wallet] = relationship()
    token: Mapped[Token] = relationship()


class SmartMoneySignal(Base):
    __tablename__ = "smart_money_signals"
    __table_args__ = (
        Index("ix_smart_money_signals_token_created", "token_id", "created_at"),
        Index("ix_smart_money_signals_type_created", "signal_type", "created_at"),
        CheckConstraint("signal_strength >= 0 AND signal_strength <= 100", name="ck_smart_money_signals_strength"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_smart_money_signals_confidence"),
        CheckConstraint(
            "signal_type IN ('ELITE_ENTRY', 'ACCUMULATION', 'SMART_MONEY_CLUSTER', 'SMART_MONEY_EXIT')",
            name="ck_smart_money_signals_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    signal_type: Mapped[str] = mapped_column(String(32))
    signal_strength: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    number_of_smart_wallets: Mapped[int] = mapped_column(Integer)
    total_capital_moved: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=0)
    supporting_data_json: Mapped[dict] = mapped_column(JSON)
    event_fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    token: Mapped[Token] = relationship()
