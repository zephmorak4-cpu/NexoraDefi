"""add candidate wallet discovery

Revision ID: c9d5f0a8e2b1
Revises: b6a4e29c7d12
Create Date: 2026-07-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d5f0a8e2b1"
down_revision: Union[str, None] = "b6a4e29c7d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_address", sa.String(length=128), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("discovery_reason", sa.String(length=255), nullable=False),
        sa.Column("wallet_type", sa.String(length=64), nullable=False),
        sa.Column("candidate_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("reputation_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("historical_accuracy_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("suspicious_score", sa.Numeric(7, 4), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chain", "wallet_address", name="uq_candidate_wallet_chain_address"),
    )
    op.create_index("ix_candidate_wallets_status_score", "candidate_wallets", ["status", "candidate_score"])
    op.create_index("ix_candidate_wallets_type_status", "candidate_wallets", ["wallet_type", "status"])

    op.create_table(
        "candidate_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(38, 18), nullable=False),
        sa.Column("usd_value", sa.Numeric(38, 2), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["candidate_wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_history_timestamp", "candidate_history", ["timestamp"])
    op.create_index("ix_candidate_history_token_timestamp", "candidate_history", ["token", "timestamp"])
    op.create_index("ix_candidate_history_wallet_timestamp", "candidate_history", ["wallet_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_candidate_history_wallet_timestamp", table_name="candidate_history")
    op.drop_index("ix_candidate_history_token_timestamp", table_name="candidate_history")
    op.drop_index("ix_candidate_history_timestamp", table_name="candidate_history")
    op.drop_table("candidate_history")
    op.drop_index("ix_candidate_wallets_type_status", table_name="candidate_wallets")
    op.drop_index("ix_candidate_wallets_status_score", table_name="candidate_wallets")
    op.drop_table("candidate_wallets")
