"""add validation and backtesting

Revision ID: f6c2e91b8a44
Revises: e1b7c9a42d30
Create Date: 2026-06-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6c2e91b8a44"
down_revision: Union[str, None] = "e1b7c9a42d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals_generated",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("decision_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market_phase", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_signal_confidence"),
        sa.CheckConstraint("decision_score >= 0 AND decision_score <= 100", name="ck_signal_decision_score"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_signals_generated_decision_type"), "signals_generated", ["decision_type"], unique=False)
    op.create_index(op.f("ix_signals_generated_generated_at"), "signals_generated", ["generated_at"], unique=False)
    op.create_index(op.f("ix_signals_generated_market_phase"), "signals_generated", ["market_phase"], unique=False)
    op.create_index(op.f("ix_signals_generated_model_version"), "signals_generated", ["model_version"], unique=False)
    op.create_index("ix_signals_generated_model_type", "signals_generated", ["model_version", "decision_type"], unique=False)
    op.create_index("ix_signals_generated_token_generated", "signals_generated", ["token_id", "generated_at"], unique=False)

    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("time_period", sa.String(length=32), nullable=False),
        sa.Column("total_signals", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("average_return", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("median_return", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("average_drawdown", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("precision", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("recall", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("f1_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("f1_score >= 0 AND f1_score <= 100", name="ck_performance_f1"),
        sa.CheckConstraint("precision >= 0 AND precision <= 100", name="ck_performance_precision"),
        sa.CheckConstraint("recall >= 0 AND recall <= 100", name="ck_performance_recall"),
        sa.CheckConstraint("win_rate >= 0 AND win_rate <= 100", name="ck_performance_win_rate"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_performance_metrics_model_version"), "performance_metrics", ["model_version"], unique=False)
    op.create_index("ix_performance_metrics_model_period", "performance_metrics", ["model_version", "time_period", "created_at"], unique=False)
    op.create_index(op.f("ix_performance_metrics_time_period"), "performance_metrics", ["time_period"], unique=False)

    op.create_table(
        "weight_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("module_name", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("reason_for_change", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_weight_history_model_version"), "weight_history", ["model_version"], unique=False)
    op.create_index(op.f("ix_weight_history_module_name"), "weight_history", ["module_name"], unique=False)
    op.create_index("ix_weight_history_model_module", "weight_history", ["model_version", "module_name", "created_at"], unique=False)

    op.create_table(
        "model_health",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("drift_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("confidence_calibration_error", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("last_validation", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("confidence_calibration_error >= 0 AND confidence_calibration_error <= 100", name="ck_model_health_calibration"),
        sa.CheckConstraint("drift_score >= 0 AND drift_score <= 100", name="ck_model_health_drift"),
        sa.CheckConstraint("status IN ('HEALTHY', 'WARNING', 'CRITICAL')", name="ck_model_health_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_health_model_version"), "model_health", ["model_version"], unique=False)
    op.create_index("ix_model_health_model_created", "model_health", ["model_version", "created_at"], unique=False)
    op.create_index(op.f("ix_model_health_status"), "model_health", ["status"], unique=False)
    op.create_index("ix_model_health_status_created", "model_health", ["status", "created_at"], unique=False)

    op.create_table(
        "signal_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("price_at_signal", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("price_after_1d", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("price_after_7d", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("price_after_30d", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("price_after_90d", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("maximum_gain", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("maximum_drawdown", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("status IN ('PENDING', 'PARTIAL', 'RESOLVED', 'INSUFFICIENT_DATA')", name="ck_signal_outcome_status"),
        sa.ForeignKeyConstraint(["signal_id"], ["signals_generated.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id"),
    )
    op.create_index("ix_signal_outcomes_signal", "signal_outcomes", ["signal_id"], unique=False)
    op.create_index(op.f("ix_signal_outcomes_status"), "signal_outcomes", ["status"], unique=False)
    op.create_index("ix_signal_outcomes_status_measured", "signal_outcomes", ["status", "measured_at"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        for table in ("signals_generated", "signal_outcomes", "performance_metrics", "weight_history", "model_health"):
            op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index("ix_signal_outcomes_status_measured", table_name="signal_outcomes")
    op.drop_index(op.f("ix_signal_outcomes_status"), table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_signal", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
    op.drop_index("ix_model_health_status_created", table_name="model_health")
    op.drop_index(op.f("ix_model_health_status"), table_name="model_health")
    op.drop_index("ix_model_health_model_created", table_name="model_health")
    op.drop_index(op.f("ix_model_health_model_version"), table_name="model_health")
    op.drop_table("model_health")
    op.drop_index("ix_weight_history_model_module", table_name="weight_history")
    op.drop_index(op.f("ix_weight_history_module_name"), table_name="weight_history")
    op.drop_index(op.f("ix_weight_history_model_version"), table_name="weight_history")
    op.drop_table("weight_history")
    op.drop_index(op.f("ix_performance_metrics_time_period"), table_name="performance_metrics")
    op.drop_index("ix_performance_metrics_model_period", table_name="performance_metrics")
    op.drop_index(op.f("ix_performance_metrics_model_version"), table_name="performance_metrics")
    op.drop_table("performance_metrics")
    op.drop_index("ix_signals_generated_token_generated", table_name="signals_generated")
    op.drop_index("ix_signals_generated_model_type", table_name="signals_generated")
    op.drop_index(op.f("ix_signals_generated_model_version"), table_name="signals_generated")
    op.drop_index(op.f("ix_signals_generated_market_phase"), table_name="signals_generated")
    op.drop_index(op.f("ix_signals_generated_generated_at"), table_name="signals_generated")
    op.drop_index(op.f("ix_signals_generated_decision_type"), table_name="signals_generated")
    op.drop_table("signals_generated")
