"""add StockPick stage1 fields — rsi_14, volume_ratio, momentum_20d, technical_score

Revision ID: 9c1d5f7e3a2b
Revises: 8b2c4f6e9d1a
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa


revision = "9c1d5f7e3a2b"
down_revision = "8b2c4f6e9d1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stock_picks", sa.Column("rsi_14", sa.Float(), nullable=True))
    op.add_column("stock_picks", sa.Column("volume_ratio", sa.Float(), nullable=True))
    op.add_column("stock_picks", sa.Column("momentum_20d", sa.Float(), nullable=True))
    op.add_column("stock_picks", sa.Column("technical_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("stock_picks", "technical_score")
    op.drop_column("stock_picks", "momentum_20d")
    op.drop_column("stock_picks", "volume_ratio")
    op.drop_column("stock_picks", "rsi_14")
