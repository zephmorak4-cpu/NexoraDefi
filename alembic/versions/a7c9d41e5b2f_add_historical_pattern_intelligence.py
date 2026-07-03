"""add historical pattern intelligence

Revision ID: a7c9d41e5b2f
Revises: 41b5fd6a3a1c
Create Date: 2026-06-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c9d41e5b2f"
down_revision: Union[str, None] = "41b5fd6a3a1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historical_token_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("market_cap", sa.Numeric(precision=38, scale=2), nullable=True),
        sa.Column("holders", sa.Integer(), nullable=False),
        sa.Column("transactions", sa.Integer(), nullable=False),
        sa.Column("volume", sa.Numeric(precision=38, scale=2), nullable=True),
        sa.Column("liquidity", sa.Numeric(precision=38, scale=2), nullable=True),
        sa.Column("smart_money_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("momentum_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("growth_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("social_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("developer_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("narrative_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", "snapshot_date", name="uq_historical_snapshot_token_date"),
    )
    op.create_index("ix_historical_snapshots_date", "historical_token_snapshots", ["snapshot_date"], unique=False)
    op.create_index("ix_historical_snapshots_token_date", "historical_token_snapshots", ["token_id", "snapshot_date"], unique=False)

    op.create_table(
        "historical_winners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("growth_multiple", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("days_to_2x", sa.Integer(), nullable=True),
        sa.Column("days_to_5x", sa.Integer(), nullable=True),
        sa.Column("days_to_10x", sa.Integer(), nullable=True),
        sa.Column("days_to_25x", sa.Integer(), nullable=True),
        sa.Column("days_to_50x", sa.Integer(), nullable=True),
        sa.Column("winner_class", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("winner_class IN ('2X', '5X', '10X', '25X', '50X', '100X')", name="ck_historical_winner_class"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", name="uq_historical_winner_token"),
    )
    op.create_index("ix_historical_winners_class", "historical_winners", ["winner_class"], unique=False)
    op.create_index(op.f("ix_historical_winners_winner_class"), "historical_winners", ["winner_class"], unique=False)

    op.create_table(
        "pattern_library",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("pattern_type", sa.String(length=64), nullable=False),
        sa.Column("feature_vector", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pattern_name"),
    )
    op.create_index("ix_pattern_library_confidence", "pattern_library", ["confidence", "created_at"], unique=False)
    op.create_index("ix_pattern_library_type", "pattern_library", ["pattern_type"], unique=False)
    op.create_index(op.f("ix_pattern_library_pattern_type"), "pattern_library", ["pattern_type"], unique=False)

    op.create_table(
        "historical_similarity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_token_id", sa.Integer(), nullable=False),
        sa.Column("historical_token_id", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("matching_features", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("similarity_score >= 0 AND similarity_score <= 100", name="ck_historical_similarity_score"),
        sa.ForeignKeyConstraint(["current_token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["historical_token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("current_token_id", "historical_token_id", name="uq_historical_similarity_pair"),
    )
    op.create_index("ix_historical_similarity_created", "historical_similarity", ["created_at"], unique=False)
    op.create_index("ix_historical_similarity_current_score", "historical_similarity", ["current_token_id", "similarity_score"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        for table in ("historical_token_snapshots", "historical_winners", "pattern_library", "historical_similarity"):
            op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index("ix_historical_similarity_current_score", table_name="historical_similarity")
    op.drop_index("ix_historical_similarity_created", table_name="historical_similarity")
    op.drop_table("historical_similarity")
    op.drop_index(op.f("ix_pattern_library_pattern_type"), table_name="pattern_library")
    op.drop_index("ix_pattern_library_type", table_name="pattern_library")
    op.drop_index("ix_pattern_library_confidence", table_name="pattern_library")
    op.drop_table("pattern_library")
    op.drop_index(op.f("ix_historical_winners_winner_class"), table_name="historical_winners")
    op.drop_index("ix_historical_winners_class", table_name="historical_winners")
    op.drop_table("historical_winners")
    op.drop_index("ix_historical_snapshots_token_date", table_name="historical_token_snapshots")
    op.drop_index("ix_historical_snapshots_date", table_name="historical_token_snapshots")
    op.drop_table("historical_token_snapshots")
