from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.entities import Token


class TokenRiskMetric(Base):
    __tablename__ = "token_risk_metrics"
    __table_args__ = (
        Index("ix_token_risk_token_calculated", "token_id", "calculated_at"),
        Index("ix_token_risk_level_calculated", "risk_level", "calculated_at"),
        CheckConstraint("holder_concentration_score >= 0 AND holder_concentration_score <= 100", name="ck_token_risk_holder"),
        CheckConstraint("liquidity_risk_score >= 0 AND liquidity_risk_score <= 100", name="ck_token_risk_liquidity"),
        CheckConstraint("volatility_risk_score >= 0 AND volatility_risk_score <= 100", name="ck_token_risk_volatility"),
        CheckConstraint("age_risk_score >= 0 AND age_risk_score <= 100", name="ck_token_risk_age"),
        CheckConstraint("smart_money_exit_risk_score >= 0 AND smart_money_exit_risk_score <= 100", name="ck_token_risk_smart_money"),
        CheckConstraint("contract_security_score >= 0 AND contract_security_score <= 100", name="ck_token_risk_contract"),
        CheckConstraint("overall_risk_score >= 0 AND overall_risk_score <= 100", name="ck_token_risk_overall"),
        CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_token_risk_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    holder_concentration_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    liquidity_risk_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    volatility_risk_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    age_risk_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    smart_money_exit_risk_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    contract_security_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    overall_risk_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    token: Mapped[Token] = relationship()


class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_risk_events_token_created", "token_id", "created_at"),
        Index("ix_risk_events_type_created", "event_type", "created_at"),
        Index("ix_risk_events_severity_created", "severity", "created_at"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_risk_events_confidence"),
        CheckConstraint(
            "event_type IN ('SMART_MONEY_EXIT', 'TOKEN_CONCENTRATION', 'LIQUIDITY_WARNING', 'EXTREME_VOLATILITY', 'CONTRACT_RISK')",
            name="ck_risk_events_type",
        ),
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_risk_events_severity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    description: Mapped[str] = mapped_column(String(512))
    supporting_data_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    token: Mapped[Token] = relationship()
