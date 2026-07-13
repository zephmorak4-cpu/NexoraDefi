"""add spot momentum engine

Revision ID: 27b4a6f95a10
Revises: a18c9e7b5132
Create Date: 2026-07-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "27b4a6f95a10"
down_revision: str | None = "a18c9e7b5132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spot_provider_health",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "capability", name="uq_spot_provider_capability"),
    )
    op.create_index("ix_spot_provider_health_provider", "spot_provider_health", ["provider"])
    op.create_index("ix_spot_provider_health_capability", "spot_provider_health", ["capability"])
    op.create_index("ix_spot_provider_health_status", "spot_provider_health", ["status"])

    op.create_table(
        "spot_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("decimals", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market_cap_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("fdv_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("liquidity_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("volume_24h_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("primary_pool_address", sa.String(length=128), nullable=True),
        sa.Column("primary_dex", sa.String(length=64), nullable=True),
        sa.Column("quote_asset", sa.String(length=32), nullable=True),
        sa.Column("data_sources", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address"),
    )
    op.create_index("ix_spot_tokens_chain", "spot_tokens", ["chain"])
    op.create_index("ix_spot_tokens_address", "spot_tokens", ["address"])

    op.create_table(
        "spot_token_pools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("pool_address", sa.String(length=128), nullable=False),
        sa.Column("dex", sa.String(length=64), nullable=True),
        sa.Column("quote_asset", sa.String(length=32), nullable=True),
        sa.Column("liquidity_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("volume_24h_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_address", "pool_address", name="uq_spot_token_pool"),
    )
    op.create_index("ix_spot_token_pools_token_address", "spot_token_pools", ["token_address"])
    op.create_index("ix_spot_token_pools_pool_address", "spot_token_pools", ["pool_address"])

    op.create_table(
        "spot_universe_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("candidates_discovered", sa.Integer(), nullable=False),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("core_count", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("exclusion_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
    )
    op.create_index("ix_spot_universe_snapshots_snapshot_id", "spot_universe_snapshots", ["snapshot_id"])

    op.create_table(
        "spot_universe_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(7, 4), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["spot_universe_snapshots.snapshot_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "token_address", name="uq_spot_universe_member"),
    )
    op.create_index("ix_spot_universe_members_snapshot_id", "spot_universe_members", ["snapshot_id"])
    op.create_index("ix_spot_universe_members_token_address", "spot_universe_members", ["token_address"])
    op.create_index("ix_spot_universe_tier_rank", "spot_universe_members", ["tier", "rank"])

    op.create_table(
        "spot_candles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("pool_address", sa.String(length=128), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(38, 12), nullable=False),
        sa.Column("high", sa.Numeric(38, 12), nullable=False),
        sa.Column("low", sa.Numeric(38, 12), nullable=False),
        sa.Column("close", sa.Numeric(38, 12), nullable=False),
        sa.Column("volume", sa.Numeric(38, 8), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_address", "pool_address", "timeframe", "timestamp", "source", name="uq_spot_candle"),
    )
    op.create_index("ix_spot_candles_token_address", "spot_candles", ["token_address"])
    op.create_index("ix_spot_candles_pool_address", "spot_candles", ["pool_address"])
    op.create_index("ix_spot_candles_timeframe", "spot_candles", ["timeframe"])
    op.create_index("ix_spot_candles_timestamp", "spot_candles", ["timestamp"])
    op.create_index("ix_spot_candle_token_timeframe_timestamp", "spot_candles", ["token_address", "timeframe", "timestamp"])

    op.create_table(
        "spot_setup_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=64), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("quality_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("reward_risk", sa.Numeric(12, 4), nullable=True),
        sa.Column("rejection_reasons", sa.JSON(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spot_setup_evaluations_scan_id", "spot_setup_evaluations", ["scan_id"])
    op.create_index("ix_spot_setup_evaluations_token_address", "spot_setup_evaluations", ["token_address"])
    op.create_index("ix_spot_setup_evaluations_decision", "spot_setup_evaluations", ["decision"])
    op.create_index("ix_spot_setup_scan_token", "spot_setup_evaluations", ["scan_id", "token_address"])

    op.create_table(
        "spot_trade_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("quality_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("reward_risk", sa.Numeric(12, 4), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("notification_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_spot_signal_fingerprint"),
    )
    op.create_index("ix_spot_trade_signals_fingerprint", "spot_trade_signals", ["fingerprint"])
    op.create_index("ix_spot_trade_signals_token_address", "spot_trade_signals", ["token_address"])

    op.create_table(
        "spot_paper_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("starting_balance_usd", sa.Numeric(38, 2), nullable=False),
        sa.Column("cash_balance_usd", sa.Numeric(38, 2), nullable=False),
        sa.Column("equity_usd", sa.Numeric(38, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "spot_paper_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signal_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("entry_price", sa.Numeric(38, 12), nullable=True),
        sa.Column("stop_loss", sa.Numeric(38, 12), nullable=False),
        sa.Column("target_1", sa.Numeric(38, 12), nullable=False),
        sa.Column("target_2", sa.Numeric(38, 12), nullable=False),
        sa.Column("target_3", sa.Numeric(38, 12), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 12), nullable=True),
        sa.Column("realized_pnl_usd", sa.Numeric(38, 2), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spot_paper_positions_signal_fingerprint", "spot_paper_positions", ["signal_fingerprint"])
    op.create_index("ix_spot_paper_positions_token_address", "spot_paper_positions", ["token_address"])
    op.create_index("ix_spot_paper_positions_state", "spot_paper_positions", ["state"])

    op.create_table(
        "spot_paper_fills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=False),
        sa.Column("fill_type", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Numeric(38, 12), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 12), nullable=False),
        sa.Column("fee_usd", sa.Numeric(38, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["position_id"], ["spot_paper_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spot_paper_fills_position_id", "spot_paper_fills", ["position_id"])

    op.create_table(
        "spot_daily_performance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", name="uq_spot_daily_performance_date"),
    )
    op.create_index("ix_spot_daily_performance_date", "spot_daily_performance", ["date"])


def downgrade() -> None:
    op.drop_index("ix_spot_daily_performance_date", table_name="spot_daily_performance")
    op.drop_table("spot_daily_performance")
    op.drop_index("ix_spot_paper_fills_position_id", table_name="spot_paper_fills")
    op.drop_table("spot_paper_fills")
    op.drop_index("ix_spot_paper_positions_state", table_name="spot_paper_positions")
    op.drop_index("ix_spot_paper_positions_token_address", table_name="spot_paper_positions")
    op.drop_index("ix_spot_paper_positions_signal_fingerprint", table_name="spot_paper_positions")
    op.drop_table("spot_paper_positions")
    op.drop_table("spot_paper_accounts")
    op.drop_index("ix_spot_trade_signals_token_address", table_name="spot_trade_signals")
    op.drop_index("ix_spot_trade_signals_fingerprint", table_name="spot_trade_signals")
    op.drop_table("spot_trade_signals")
    op.drop_index("ix_spot_setup_scan_token", table_name="spot_setup_evaluations")
    op.drop_index("ix_spot_setup_evaluations_decision", table_name="spot_setup_evaluations")
    op.drop_index("ix_spot_setup_evaluations_token_address", table_name="spot_setup_evaluations")
    op.drop_index("ix_spot_setup_evaluations_scan_id", table_name="spot_setup_evaluations")
    op.drop_table("spot_setup_evaluations")
    op.drop_index("ix_spot_candle_token_timeframe_timestamp", table_name="spot_candles")
    op.drop_index("ix_spot_candles_timestamp", table_name="spot_candles")
    op.drop_index("ix_spot_candles_timeframe", table_name="spot_candles")
    op.drop_index("ix_spot_candles_pool_address", table_name="spot_candles")
    op.drop_index("ix_spot_candles_token_address", table_name="spot_candles")
    op.drop_table("spot_candles")
    op.drop_index("ix_spot_universe_tier_rank", table_name="spot_universe_members")
    op.drop_index("ix_spot_universe_members_token_address", table_name="spot_universe_members")
    op.drop_index("ix_spot_universe_members_snapshot_id", table_name="spot_universe_members")
    op.drop_table("spot_universe_members")
    op.drop_index("ix_spot_universe_snapshots_snapshot_id", table_name="spot_universe_snapshots")
    op.drop_table("spot_universe_snapshots")
    op.drop_index("ix_spot_token_pools_pool_address", table_name="spot_token_pools")
    op.drop_index("ix_spot_token_pools_token_address", table_name="spot_token_pools")
    op.drop_table("spot_token_pools")
    op.drop_index("ix_spot_tokens_address", table_name="spot_tokens")
    op.drop_index("ix_spot_tokens_chain", table_name="spot_tokens")
    op.drop_table("spot_tokens")
    op.drop_index("ix_spot_provider_health_status", table_name="spot_provider_health")
    op.drop_index("ix_spot_provider_health_capability", table_name="spot_provider_health")
    op.drop_index("ix_spot_provider_health_provider", table_name="spot_provider_health")
    op.drop_table("spot_provider_health")
