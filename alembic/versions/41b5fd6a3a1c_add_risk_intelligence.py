"""add risk intelligence

Revision ID: 41b5fd6a3a1c
Revises: 0886562e408b
Create Date: 2026-06-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "41b5fd6a3a1c"
down_revision: Union[str, None] = "0886562e408b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_risk_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("holder_concentration_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("liquidity_risk_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("volatility_risk_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("age_risk_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("smart_money_exit_risk_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("contract_security_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("overall_risk_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("age_risk_score >= 0 AND age_risk_score <= 100", name="ck_token_risk_age"),
        sa.CheckConstraint("contract_security_score >= 0 AND contract_security_score <= 100", name="ck_token_risk_contract"),
        sa.CheckConstraint("holder_concentration_score >= 0 AND holder_concentration_score <= 100", name="ck_token_risk_holder"),
        sa.CheckConstraint("liquidity_risk_score >= 0 AND liquidity_risk_score <= 100", name="ck_token_risk_liquidity"),
        sa.CheckConstraint("overall_risk_score >= 0 AND overall_risk_score <= 100", name="ck_token_risk_overall"),
        sa.CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_token_risk_level"),
        sa.CheckConstraint("smart_money_exit_risk_score >= 0 AND smart_money_exit_risk_score <= 100", name="ck_token_risk_smart_money"),
        sa.CheckConstraint("volatility_risk_score >= 0 AND volatility_risk_score <= 100", name="ck_token_risk_volatility"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_token_risk_level_calculated", "token_risk_metrics", ["risk_level", "calculated_at"], unique=False)
    op.create_index("ix_token_risk_token_calculated", "token_risk_metrics", ["token_id", "calculated_at"], unique=False)
    op.create_index(op.f("ix_token_risk_metrics_risk_level"), "token_risk_metrics", ["risk_level"], unique=False)

    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("supporting_data_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_risk_events_confidence"),
        sa.CheckConstraint(
            "event_type IN ('SMART_MONEY_EXIT', 'TOKEN_CONCENTRATION', 'LIQUIDITY_WARNING', 'EXTREME_VOLATILITY', 'CONTRACT_RISK')",
            name="ck_risk_events_type",
        ),
        sa.CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_risk_events_severity"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risk_events_severity"), "risk_events", ["severity"], unique=False)
    op.create_index("ix_risk_events_severity_created", "risk_events", ["severity", "created_at"], unique=False)
    op.create_index("ix_risk_events_token_created", "risk_events", ["token_id", "created_at"], unique=False)
    op.create_index("ix_risk_events_type_created", "risk_events", ["event_type", "created_at"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        for table in ("token_risk_metrics", "risk_events"):
            op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index("ix_risk_events_type_created", table_name="risk_events")
    op.drop_index("ix_risk_events_token_created", table_name="risk_events")
    op.drop_index("ix_risk_events_severity_created", table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_severity"), table_name="risk_events")
    op.drop_table("risk_events")
    op.drop_index(op.f("ix_token_risk_metrics_risk_level"), table_name="token_risk_metrics")
    op.drop_index("ix_token_risk_token_calculated", table_name="token_risk_metrics")
    op.drop_index("ix_token_risk_level_calculated", table_name="token_risk_metrics")
    op.drop_table("token_risk_metrics")
