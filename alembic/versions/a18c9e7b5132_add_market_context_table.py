"""add market context table

Revision ID: a18c9e7b5132
Revises: f9a2c4b7d801
Create Date: 2026-07-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a18c9e7b5132"
down_revision: Union[str, None] = "f9a2c4b7d801"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_context",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_position_id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("entry_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market_cap_entry", sa.Numeric(38, 2), nullable=True),
        sa.Column("market_cap_exit", sa.Numeric(38, 2), nullable=True),
        sa.Column("liquidity_entry", sa.Numeric(38, 2), nullable=True),
        sa.Column("liquidity_exit", sa.Numeric(38, 2), nullable=True),
        sa.Column("holder_count_entry", sa.Integer(), nullable=True),
        sa.Column("holder_count_exit", sa.Integer(), nullable=True),
        sa.Column("daily_volume_entry", sa.Numeric(38, 2), nullable=True),
        sa.Column("daily_volume_exit", sa.Numeric(38, 2), nullable=True),
        sa.Column("token_age_entry", sa.Numeric(18, 6), nullable=True),
        sa.Column("token_age_exit", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_entry", sa.Numeric(38, 18), nullable=True),
        sa.Column("price_exit", sa.Numeric(38, 18), nullable=True),
        sa.Column("market_sentiment", sa.String(length=64), nullable=False),
        sa.Column("wallet_consensus", sa.String(length=255), nullable=False),
        sa.Column("context_score", sa.Numeric(7, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["wallet_position_id"], ["wallet_positions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_position_id", name="uq_market_context_wallet_position"),
    )
    op.create_index("ix_market_context_wallet_position_id", "market_context", ["wallet_position_id"])
    op.create_index("ix_market_context_token_address", "market_context", ["token_address"])
    op.create_index("ix_market_context_token_entry", "market_context", ["token_address", "entry_timestamp"])
    op.create_index("ix_market_context_score", "market_context", ["context_score", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_market_context_score", table_name="market_context")
    op.drop_index("ix_market_context_token_entry", table_name="market_context")
    op.drop_index("ix_market_context_token_address", table_name="market_context")
    op.drop_index("ix_market_context_wallet_position_id", table_name="market_context")
    op.drop_table("market_context")
