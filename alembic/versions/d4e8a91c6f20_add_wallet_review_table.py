"""add wallet review table

Revision ID: d4e8a91c6f20
Revises: c9d5f0a8e2b1
Create Date: 2026-07-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e8a91c6f20"
down_revision: Union[str, None] = "c9d5f0a8e2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_for_signals", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["candidate_wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_id", name="uq_wallet_review_wallet"),
    )


def downgrade() -> None:
    op.drop_table("wallet_review")
