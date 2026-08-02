"""cascade position FK on balance_transactions + trading_decisions

Revision ID: b5c6d7e8f901
Revises: a4b5c6d7e8f9
Create Date: 2026-08-02
"""
from alembic import op


revision = "b5c6d7e8f901"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("balance_transactions_position_id_fkey", "balance_transactions", type_="foreignkey")
    op.create_foreign_key(
        "balance_transactions_position_id_fkey",
        "balance_transactions", "portfolio_positions",
        ["position_id"], ["id"], ondelete="CASCADE",
    )
    op.drop_constraint("trading_decisions_position_id_fkey", "trading_decisions", type_="foreignkey")
    op.create_foreign_key(
        "trading_decisions_position_id_fkey",
        "trading_decisions", "portfolio_positions",
        ["position_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("trading_decisions_position_id_fkey", "trading_decisions", type_="foreignkey")
    op.create_foreign_key(
        "trading_decisions_position_id_fkey",
        "trading_decisions", "portfolio_positions",
        ["position_id"], ["id"],
    )
    op.drop_constraint("balance_transactions_position_id_fkey", "balance_transactions", type_="foreignkey")
    op.create_foreign_key(
        "balance_transactions_position_id_fkey",
        "balance_transactions", "portfolio_positions",
        ["position_id"], ["id"],
    )
