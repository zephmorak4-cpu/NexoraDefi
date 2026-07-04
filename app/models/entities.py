from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Token(TimestampMixin, Base):
    __tablename__ = "tokens"
    __table_args__ = (UniqueConstraint("chain", "blockchain_address", name="uq_token_chain_address"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    blockchain_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    chain: Mapped[str] = mapped_column(String(32), default="solana")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Wallet(TimestampMixin, Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("chain", "wallet_address", name="uq_wallet_chain_address"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String(128))
    chain: Mapped[str] = mapped_column(String(32), default="solana")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("wallet_id", "external_id", name="uq_transaction_wallet_external"),
        Index("ix_transactions_timestamp", "timestamp"),
        Index("ix_transactions_wallet_token_timestamp", "wallet_id", "token_id", "timestamp"),
        Index("ix_transactions_wallet_type_timestamp", "wallet_id", "transaction_type", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    token_id: Mapped[int | None] = mapped_column(ForeignKey("tokens.id", ondelete="SET NULL"))
    external_id: Mapped[str] = mapped_column(String(160))
    transaction_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    wallet: Mapped[Wallet] = relationship()
    token: Mapped[Token | None] = relationship()


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("token_id", "timestamp", name="uq_price_token_timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    liquidity_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 2), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SocialSignal(Base):
    __tablename__ = "social_signals"
    __table_args__ = (
        UniqueConstraint("token_id", "source", "timestamp", name="uq_social_token_source_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int | None] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(64))
    mentions: Mapped[int] = mapped_column(default=0)
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketSignal(Base):
    __tablename__ = "market_signals"
    __table_args__ = (
        UniqueConstraint("market_name", "metric", "timestamp", name="uq_market_metric_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_name: Mapped[str] = mapped_column(String(128))
    metric: Mapped[str] = mapped_column(String(128))
    value: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    token_id: Mapped[int | None] = mapped_column(ForeignKey("tokens.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    subscription_type: Mapped[str] = mapped_column(String(32), default="free")


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
