"""add alpha provider snapshots

Revision ID: f9a2c4b7d801
Revises: d8e7a31f42c0
Create Date: 2026-07-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9a2c4b7d801"
down_revision: Union[str, None] = "d8e7a31f42c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alpha_scanned_tokens", sa.Column("scan_id", sa.String(length=64), nullable=True))
    op.create_index("ix_alpha_scanned_tokens_scan_id", "alpha_scanned_tokens", ["scan_id"])
    op.add_column("alpha_alert_history", sa.Column("scan_id", sa.String(length=64), nullable=True))
    op.create_index("ix_alpha_alert_history_scan_id", "alpha_alert_history", ["scan_id"])
    op.create_table(
        "alpha_provider_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=64), nullable=True),
        sa.Column("token_address", sa.String(length=128), nullable=False),
        sa.Column("pair_address", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("raw_response_json", sa.JSON(), nullable=True),
        sa.Column("normalized_data_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alpha_provider_snapshots_scan_id", "alpha_provider_snapshots", ["scan_id"])
    op.create_index("ix_alpha_provider_snapshots_token_address", "alpha_provider_snapshots", ["token_address"])
    op.create_index("ix_alpha_provider_snapshots_provider", "alpha_provider_snapshots", ["provider"])
    op.create_index(
        "ix_alpha_provider_snapshot_token_created",
        "alpha_provider_snapshots",
        ["token_address", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_alpha_provider_snapshot_token_created", table_name="alpha_provider_snapshots")
    op.drop_index("ix_alpha_provider_snapshots_provider", table_name="alpha_provider_snapshots")
    op.drop_index("ix_alpha_provider_snapshots_token_address", table_name="alpha_provider_snapshots")
    op.drop_index("ix_alpha_provider_snapshots_scan_id", table_name="alpha_provider_snapshots")
    op.drop_table("alpha_provider_snapshots")
    op.drop_index("ix_alpha_alert_history_scan_id", table_name="alpha_alert_history")
    op.drop_column("alpha_alert_history", "scan_id")
    op.drop_index("ix_alpha_scanned_tokens_scan_id", table_name="alpha_scanned_tokens")
    op.drop_column("alpha_scanned_tokens", "scan_id")
