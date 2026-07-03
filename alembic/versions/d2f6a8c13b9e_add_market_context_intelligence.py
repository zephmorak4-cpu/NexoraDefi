"""add market context intelligence

Revision ID: d2f6a8c13b9e
Revises: a7c9d41e5b2f
Create Date: 2026-06-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f6a8c13b9e"
down_revision: Union[str, None] = "a7c9d41e5b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_context",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_sentiment", sa.String(length=32), nullable=False),
        sa.Column("btc_trend", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("eth_trend", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("market_strength", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("market_volatility", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("capital_flow_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("risk_appetite_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("overall_market_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("market_phase", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("btc_trend >= 0 AND btc_trend <= 100", name="ck_market_context_btc"),
        sa.CheckConstraint("capital_flow_score >= 0 AND capital_flow_score <= 100", name="ck_market_context_capital"),
        sa.CheckConstraint("eth_trend >= 0 AND eth_trend <= 100", name="ck_market_context_eth"),
        sa.CheckConstraint("market_phase IN ('STRONG_BULL', 'BULL', 'RECOVERY', 'NEUTRAL', 'CORRECTION', 'BEAR', 'CAPITULATION')", name="ck_market_context_phase"),
        sa.CheckConstraint("market_sentiment IN ('FEAR', 'NEUTRAL', 'GREED', 'EXTREME_GREED')", name="ck_market_context_sentiment"),
        sa.CheckConstraint("market_strength >= 0 AND market_strength <= 100", name="ck_market_context_strength"),
        sa.CheckConstraint("market_volatility >= 0 AND market_volatility <= 100", name="ck_market_context_volatility"),
        sa.CheckConstraint("overall_market_score >= 0 AND overall_market_score <= 100", name="ck_market_context_overall"),
        sa.CheckConstraint("risk_appetite_score >= 0 AND risk_appetite_score <= 100", name="ck_market_context_risk_appetite"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_context_created", "market_context", ["created_at"], unique=False)
    op.create_index("ix_market_context_phase_created", "market_context", ["market_phase", "created_at"], unique=False)
    op.create_index(op.f("ix_market_context_market_phase"), "market_context", ["market_phase"], unique=False)
    op.create_index(op.f("ix_market_context_market_sentiment"), "market_context", ["market_sentiment"], unique=False)

    op.create_table(
        "sector_strength",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sector_name", sa.String(length=64), nullable=False),
        sa.Column("strength_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("momentum_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("capital_flow", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("social_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("capital_flow >= 0 AND capital_flow <= 100", name="ck_sector_strength_capital"),
        sa.CheckConstraint("momentum_score >= 0 AND momentum_score <= 100", name="ck_sector_strength_momentum"),
        sa.CheckConstraint("social_score >= 0 AND social_score <= 100", name="ck_sector_strength_social"),
        sa.CheckConstraint("strength_score >= 0 AND strength_score <= 100", name="ck_sector_strength_score"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sector_strength_name_created", "sector_strength", ["sector_name", "created_at"], unique=False)
    op.create_index("ix_sector_strength_rank", "sector_strength", ["strength_score", "created_at"], unique=False)
    op.create_index(op.f("ix_sector_strength_sector_name"), "sector_strength", ["sector_name"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        for table in ("market_context", "sector_strength"):
            op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index(op.f("ix_sector_strength_sector_name"), table_name="sector_strength")
    op.drop_index("ix_sector_strength_rank", table_name="sector_strength")
    op.drop_index("ix_sector_strength_name_created", table_name="sector_strength")
    op.drop_table("sector_strength")
    op.drop_index(op.f("ix_market_context_market_sentiment"), table_name="market_context")
    op.drop_index(op.f("ix_market_context_market_phase"), table_name="market_context")
    op.drop_index("ix_market_context_phase_created", table_name="market_context")
    op.drop_index("ix_market_context_created", table_name="market_context")
    op.drop_table("market_context")
