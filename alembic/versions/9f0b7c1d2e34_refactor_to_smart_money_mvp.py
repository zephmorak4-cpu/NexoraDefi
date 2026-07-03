"""refactor to smart money mvp

Revision ID: 9f0b7c1d2e34
Revises: f6c2e91b8a44
Create Date: 2026-07-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f0b7c1d2e34"
down_revision: Union[str, None] = "f6c2e91b8a44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REMOVED_TABLES = (
    "signal_outcomes",
    "signals_generated",
    "performance_metrics",
    "weight_history",
    "model_health",
    "decision_history",
    "decision_analysis",
    "confidence_calibration",
    "sector_strength",
    "market_context",
    "historical_similarity",
    "historical_winners",
    "historical_token_snapshots",
    "pattern_library",
    "opportunity_signals",
)


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table in REMOVED_TABLES:
        if table in existing_tables:
            op.drop_table(table)


def downgrade() -> None:
    # The MVP migration intentionally removes advanced/non-MVP data products.
    # Restore a pre-MVP database by downgrading to the previous revision before applying this migration.
    pass
