"""add decision intelligence

Revision ID: e1b7c9a42d30
Revises: d2f6a8c13b9e
Create Date: 2026-06-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1b7c9a42d30"
down_revision: Union[str, None] = "d2f6a8c13b9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DECISION_TYPES = (
    "STRONG BUY CANDIDATE",
    "BUY CANDIDATE",
    "SMALL SPECULATIVE POSITION",
    "ADD TO WATCHLIST",
    "WAIT FOR CONFIRMATION",
    "HOLD",
    "REDUCE POSITION",
    "EXIT WATCHLIST",
    "AVOID",
)


def decision_check(column: str) -> str:
    return f"{column} IN ({', '.join(repr(item) for item in DECISION_TYPES)})"


def upgrade() -> None:
    op.create_table(
        "decision_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("smart_money_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("growth_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("momentum_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("historical_pattern_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("market_context_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("overall_decision_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("position_size", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("portfolio_risk", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_decision_confidence"),
        sa.CheckConstraint("growth_score >= 0 AND growth_score <= 100", name="ck_decision_growth"),
        sa.CheckConstraint("historical_pattern_score >= 0 AND historical_pattern_score <= 100", name="ck_decision_historical"),
        sa.CheckConstraint("market_context_score >= 0 AND market_context_score <= 100", name="ck_decision_market"),
        sa.CheckConstraint("momentum_score >= 0 AND momentum_score <= 100", name="ck_decision_momentum"),
        sa.CheckConstraint("overall_decision_score >= 0 AND overall_decision_score <= 100", name="ck_decision_overall"),
        sa.CheckConstraint("position_size >= 0 AND position_size <= 100", name="ck_decision_position_size"),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_decision_risk"),
        sa.CheckConstraint("smart_money_score >= 0 AND smart_money_score <= 100", name="ck_decision_smart_money"),
        sa.CheckConstraint(decision_check("decision_type"), name="ck_decision_type"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decision_analysis_rank", "decision_analysis", ["overall_decision_score", "confidence_score", "created_at"], unique=False)
    op.create_index("ix_decision_analysis_token_created", "decision_analysis", ["token_id", "created_at"], unique=False)
    op.create_index("ix_decision_analysis_type_created", "decision_analysis", ["decision_type", "created_at"], unique=False)
    op.create_index(op.f("ix_decision_analysis_decision_type"), "decision_analysis", ["decision_type"], unique=False)

    op.create_table(
        "decision_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("market_phase", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_return", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("days_until_resolution", sa.Integer(), nullable=True),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_decision_history_confidence"),
        sa.CheckConstraint(decision_check("decision_type"), name="ck_decision_history_type"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_history_decision_type"), "decision_history", ["decision_type"], unique=False)
    op.create_index("ix_decision_history_resolution", "decision_history", ["resolved", "created_at"], unique=False)
    op.create_index(op.f("ix_decision_history_resolved"), "decision_history", ["resolved"], unique=False)
    op.create_index("ix_decision_history_token_created", "decision_history", ["token_id", "created_at"], unique=False)
    op.create_index("ix_decision_history_type_created", "decision_history", ["decision_type", "created_at"], unique=False)

    op.create_table(
        "confidence_calibration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("decision_range", sa.String(length=32), nullable=False),
        sa.Column("historical_accuracy", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("calibration_factor", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("calibration_factor >= 0 AND calibration_factor <= 2", name="ck_calibration_factor"),
        sa.CheckConstraint("historical_accuracy >= 0 AND historical_accuracy <= 100", name="ck_calibration_accuracy"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_confidence_calibration_model_range", "confidence_calibration", ["model_version", "decision_range"], unique=False)
    op.create_index(op.f("ix_confidence_calibration_decision_range"), "confidence_calibration", ["decision_range"], unique=False)
    op.create_index(op.f("ix_confidence_calibration_model_version"), "confidence_calibration", ["model_version"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        for table in ("decision_analysis", "decision_history", "confidence_calibration"):
            op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index(op.f("ix_confidence_calibration_model_version"), table_name="confidence_calibration")
    op.drop_index(op.f("ix_confidence_calibration_decision_range"), table_name="confidence_calibration")
    op.drop_index("ix_confidence_calibration_model_range", table_name="confidence_calibration")
    op.drop_table("confidence_calibration")
    op.drop_index("ix_decision_history_type_created", table_name="decision_history")
    op.drop_index("ix_decision_history_token_created", table_name="decision_history")
    op.drop_index(op.f("ix_decision_history_resolved"), table_name="decision_history")
    op.drop_index("ix_decision_history_resolution", table_name="decision_history")
    op.drop_index(op.f("ix_decision_history_decision_type"), table_name="decision_history")
    op.drop_table("decision_history")
    op.drop_index(op.f("ix_decision_analysis_decision_type"), table_name="decision_analysis")
    op.drop_index("ix_decision_analysis_type_created", table_name="decision_analysis")
    op.drop_index("ix_decision_analysis_token_created", table_name="decision_analysis")
    op.drop_index("ix_decision_analysis_rank", table_name="decision_analysis")
    op.drop_table("decision_analysis")
