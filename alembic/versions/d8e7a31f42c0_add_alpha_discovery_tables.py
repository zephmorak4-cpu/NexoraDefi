"""add alpha discovery tables

Revision ID: d8e7a31f42c0
Revises: c6e4b7a2d901
Create Date: 2026-07-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e7a31f42c0"
down_revision: Union[str, None] = "c6e4b7a2d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alpha_scanned_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("pair_address", sa.String(length=128), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("creator_wallet", sa.String(length=128), nullable=True),
        sa.Column("launch_time", sa.String(length=64), nullable=True),
        sa.Column("dex", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("liquidity_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("market_cap_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("price_usd", sa.Numeric(38, 12), nullable=True),
        sa.Column("volume_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("buys", sa.Integer(), nullable=False),
        sa.Column("sells", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("should_alert", sa.Boolean(), nullable=False),
        sa.Column("rejection_reasons", sa.JSON(), nullable=False),
        sa.Column("agent_scores", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_address", "pair_address", name="uq_alpha_scanned_token_pair"),
    )
    op.create_index("ix_alpha_scanned_tokens_decision", "alpha_scanned_tokens", ["decision", "last_seen_at"])
    op.create_index("ix_alpha_scanned_tokens_token_address", "alpha_scanned_tokens", ["token_address"])
    op.create_table(
        "alpha_alert_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("final_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alpha_alert_history_token_address", "alpha_alert_history", ["token_address"])
    op.create_index("ix_alpha_alert_token_created", "alpha_alert_history", ["token_address", "created_at"])
    op.create_table(
        "alpha_watchlist_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("final_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_address", name="uq_alpha_watchlist_token"),
    )
    op.create_index("ix_alpha_watchlist_tokens_token_address", "alpha_watchlist_tokens", ["token_address"])
    op.create_table(
        "alpha_smart_wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("score", sa.Numeric(7, 4), nullable=False),
        sa.Column("win_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address", name="uq_alpha_smart_wallet_address"),
    )
    op.create_index("ix_alpha_smart_wallets_address", "alpha_smart_wallets", ["address"])


def downgrade() -> None:
    op.drop_index("ix_alpha_smart_wallets_address", table_name="alpha_smart_wallets")
    op.drop_table("alpha_smart_wallets")
    op.drop_index("ix_alpha_watchlist_tokens_token_address", table_name="alpha_watchlist_tokens")
    op.drop_table("alpha_watchlist_tokens")
    op.drop_index("ix_alpha_alert_token_created", table_name="alpha_alert_history")
    op.drop_index("ix_alpha_alert_history_token_address", table_name="alpha_alert_history")
    op.drop_table("alpha_alert_history")
    op.drop_index("ix_alpha_scanned_tokens_token_address", table_name="alpha_scanned_tokens")
    op.drop_index("ix_alpha_scanned_tokens_decision", table_name="alpha_scanned_tokens")
    op.drop_table("alpha_scanned_tokens")
