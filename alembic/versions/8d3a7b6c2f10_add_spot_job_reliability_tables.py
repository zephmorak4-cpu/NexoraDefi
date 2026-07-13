"""add spot job reliability tables

Revision ID: 8d3a7b6c2f10
Revises: 27b4a6f95a10
Create Date: 2026-07-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d3a7b6c2f10"
down_revision: str | None = "27b4a6f95a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spot_job_locks",
        sa.Column("job_name", sa.String(length=64), nullable=False),
        sa.Column("lock_key", sa.String(length=128), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("job_name"),
    )
    op.create_index("ix_spot_job_locks_expires_at", "spot_job_locks", ["expires_at"])

    op.create_table(
        "spot_job_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_name", sa.String(length=64), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("build_version", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_name", "scheduled_for", name="uq_spot_job_execution_window"),
    )
    op.create_index("ix_spot_job_executions_job_name", "spot_job_executions", ["job_name"])
    op.create_index("ix_spot_job_executions_scheduled_for", "spot_job_executions", ["scheduled_for"])
    op.create_index("ix_spot_job_executions_status", "spot_job_executions", ["status"])
    op.create_index("ix_spot_job_execution_name_status", "spot_job_executions", ["job_name", "status"])

    op.create_table(
        "spot_system_incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("component", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spot_system_incidents_severity", "spot_system_incidents", ["severity"])
    op.create_index("ix_spot_system_incidents_component", "spot_system_incidents", ["component"])
    op.create_index("ix_spot_system_incidents_status", "spot_system_incidents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_spot_system_incidents_status", table_name="spot_system_incidents")
    op.drop_index("ix_spot_system_incidents_component", table_name="spot_system_incidents")
    op.drop_index("ix_spot_system_incidents_severity", table_name="spot_system_incidents")
    op.drop_table("spot_system_incidents")
    op.drop_index("ix_spot_job_execution_name_status", table_name="spot_job_executions")
    op.drop_index("ix_spot_job_executions_status", table_name="spot_job_executions")
    op.drop_index("ix_spot_job_executions_scheduled_for", table_name="spot_job_executions")
    op.drop_index("ix_spot_job_executions_job_name", table_name="spot_job_executions")
    op.drop_table("spot_job_executions")
    op.drop_index("ix_spot_job_locks_expires_at", table_name="spot_job_locks")
    op.drop_table("spot_job_locks")
