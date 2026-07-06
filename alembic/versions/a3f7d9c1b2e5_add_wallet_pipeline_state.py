"""add wallet pipeline state

Revision ID: a3f7d9c1b2e5
Revises: d4e8a91c6f20
Create Date: 2026-07-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f7d9c1b2e5"
down_revision: Union[str, None] = "d4e8a91c6f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate_wallets", sa.Column("pipeline_stage", sa.String(length=48), nullable=False, server_default="DISCOVERED"))
    op.add_column("candidate_wallets", sa.Column("pipeline_status", sa.String(length=64), nullable=False, server_default="PENDING"))
    op.add_column("candidate_wallets", sa.Column("pipeline_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_wallets", "pipeline_error")
    op.drop_column("candidate_wallets", "pipeline_status")
    op.drop_column("candidate_wallets", "pipeline_stage")
