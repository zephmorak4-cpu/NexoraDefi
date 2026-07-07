"""extend wallet positions for reconstruction

Revision ID: c6e4b7a2d901
Revises: b8c1f4a9d2e6
Create Date: 2026-07-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6e4b7a2d901"
down_revision: Union[str, None] = "b8c1f4a9d2e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("wallet_positions") as batch_op:
        batch_op.alter_column("wallet_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("token_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("candidate_wallet_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("token_address", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("token_symbol", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("final_exit_time", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("first_buy_signature", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("last_sell_signature", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("average_exit_price", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("quantity_bought", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("quantity_sold", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("remaining_quantity", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("position_status", sa.String(length=32), nullable=False, server_default="OPEN"))
        batch_op.add_column(sa.Column("holding_period", sa.Numeric(18, 6), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("realized_pnl", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("unrealized_pnl", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("realized_roi", sa.Numeric(18, 6), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("maximum_position_size", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("maximum_drawdown", sa.Numeric(18, 6), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("maximum_gain", sa.Numeric(18, 6), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("number_of_buys", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("number_of_sells", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("accumulation_events", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("distribution_events", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("largest_buy", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("largest_sell", sa.Numeric(38, 18), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("position_classification", sa.String(length=64), nullable=False, server_default="Unknown"))
        batch_op.add_column(sa.Column("position_quality_score", sa.Numeric(7, 4), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("ai_analysis", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False))
        batch_op.create_foreign_key("fk_wallet_positions_candidate_wallet", "candidate_wallets", ["candidate_wallet_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_wallet_positions_candidate_token", "wallet_positions", ["candidate_wallet_id", "token_address"])


def downgrade() -> None:
    op.drop_index("ix_wallet_positions_candidate_token", table_name="wallet_positions")
    with op.batch_alter_table("wallet_positions") as batch_op:
        batch_op.drop_constraint("fk_wallet_positions_candidate_wallet", type_="foreignkey")
        for column in (
            "updated_at",
            "created_at",
            "ai_analysis",
            "position_quality_score",
            "position_classification",
            "largest_sell",
            "largest_buy",
            "distribution_events",
            "accumulation_events",
            "number_of_sells",
            "number_of_buys",
            "maximum_gain",
            "maximum_drawdown",
            "maximum_position_size",
            "realized_roi",
            "unrealized_pnl",
            "realized_pnl",
            "holding_period",
            "position_status",
            "remaining_quantity",
            "quantity_sold",
            "quantity_bought",
            "average_exit_price",
            "last_sell_signature",
            "first_buy_signature",
            "final_exit_time",
            "entry_time",
            "token_symbol",
            "token_address",
            "candidate_wallet_id",
        ):
            batch_op.drop_column(column)
        batch_op.alter_column("token_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("wallet_id", existing_type=sa.Integer(), nullable=False)
