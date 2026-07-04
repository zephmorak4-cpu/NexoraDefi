"""add solana smart money tables

Revision ID: b6a4e29c7d12
Revises: 9f0b7c1d2e34
Create Date: 2026-07-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6a4e29c7d12"
down_revision: Union[str, None] = "9f0b7c1d2e34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracked_wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_address", sa.String(length=128), nullable=False),
        sa.Column("wallet_name", sa.String(length=128), nullable=True),
        sa.Column("wallet_label", sa.String(length=128), nullable=True),
        sa.Column("wallet_category", sa.String(length=64), nullable=True),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reputation_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chain", "wallet_address", name="uq_tracked_wallet_chain_address"),
    )
    op.create_index("ix_tracked_wallets_chain_status", "tracked_wallets", ["chain", "status"])

    op.create_table(
        "wallet_activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("token_symbol", sa.String(length=32), nullable=False),
        sa.Column("transaction_signature", sa.String(length=160), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(38, 18), nullable=False),
        sa.Column("usd_value", sa.Numeric(38, 2), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["tracked_wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_id", "transaction_signature", "token_address", name="uq_wallet_activity_event"),
    )
    op.create_index("ix_wallet_activity_timestamp", "wallet_activity", ["timestamp"])
    op.create_index("ix_wallet_activity_token_timestamp", "wallet_activity", ["token_address", "timestamp"])
    op.create_index("ix_wallet_activity_wallet_timestamp", "wallet_activity", ["wallet_id", "timestamp"])

    op.create_table(
        "token_quality",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("token_symbol", sa.String(length=32), nullable=False),
        sa.Column("quality_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("liquidity_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("volume_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("holder_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("age_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("market_cap_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("risk_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quality_score >= 0 AND quality_score <= 100", name="ck_token_quality_score"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_address", name="uq_token_quality_address"),
    )
    op.create_index("ix_token_quality_calculated_at", "token_quality", ["calculated_at"])
    op.create_index("ix_token_quality_score", "token_quality", ["quality_score", "calculated_at"])


def downgrade() -> None:
    op.drop_index("ix_token_quality_score", table_name="token_quality")
    op.drop_index("ix_token_quality_calculated_at", table_name="token_quality")
    op.drop_table("token_quality")
    op.drop_index("ix_wallet_activity_wallet_timestamp", table_name="wallet_activity")
    op.drop_index("ix_wallet_activity_token_timestamp", table_name="wallet_activity")
    op.drop_index("ix_wallet_activity_timestamp", table_name="wallet_activity")
    op.drop_table("wallet_activity")
    op.drop_index("ix_tracked_wallets_chain_status", table_name="tracked_wallets")
    op.drop_table("tracked_wallets")
