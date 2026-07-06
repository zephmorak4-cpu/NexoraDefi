"""add wallet pipeline evidence

Revision ID: b8c1f4a9d2e6
Revises: a3f7d9c1b2e5
Create Date: 2026-07-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c1f4a9d2e6"
down_revision: Union[str, None] = "a3f7d9c1b2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate_history", sa.Column("signature", sa.String(length=128), nullable=True))
    op.add_column("candidate_history", sa.Column("direction", sa.String(length=16), nullable=True))
    op.add_column("candidate_history", sa.Column("dex", sa.String(length=64), nullable=True))
    op.add_column("candidate_history", sa.Column("fees", sa.Numeric(38, 18), nullable=True))
    op.add_column("candidate_history", sa.Column("counterparty", sa.String(length=128), nullable=True))
    op.create_table(
        "candidate_portfolio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("total_value_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("largest_position_token", sa.String(length=128), nullable=True),
        sa.Column("largest_position_usd", sa.Numeric(38, 2), nullable=True),
        sa.Column("top_10_holdings", sa.Text(), nullable=True),
        sa.Column("stablecoin_allocation", sa.Numeric(7, 4), nullable=True),
        sa.Column("portfolio_concentration", sa.Numeric(7, 4), nullable=True),
        sa.Column("zero_assets_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["candidate_wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_portfolio_wallet_created", "candidate_portfolio_snapshots", ["wallet_id", "created_at"])
    op.create_table(
        "candidate_token_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("purchase_count", sa.Integer(), nullable=False),
        sa.Column("sale_count", sa.Integer(), nullable=False),
        sa.Column("average_entry_usd", sa.Numeric(38, 8), nullable=True),
        sa.Column("average_exit_usd", sa.Numeric(38, 8), nullable=True),
        sa.Column("holding_duration_days", sa.Numeric(18, 6), nullable=True),
        sa.Column("roi", sa.Numeric(18, 6), nullable=True),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["candidate_wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_id", "token", name="uq_candidate_token_history_wallet_token"),
    )
    op.create_index("ix_candidate_token_history_wallet", "candidate_token_history", ["wallet_id"])


def downgrade() -> None:
    op.drop_index("ix_candidate_token_history_wallet", table_name="candidate_token_history")
    op.drop_table("candidate_token_history")
    op.drop_index("ix_candidate_portfolio_wallet_created", table_name="candidate_portfolio_snapshots")
    op.drop_table("candidate_portfolio_snapshots")
    op.drop_column("candidate_history", "counterparty")
    op.drop_column("candidate_history", "fees")
    op.drop_column("candidate_history", "dex")
    op.drop_column("candidate_history", "direction")
    op.drop_column("candidate_history", "signature")
