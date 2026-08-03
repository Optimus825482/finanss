"""add source (trade engine) to portfolio_positions

Revision ID: c6d7e8f901ab
Revises: b5c6d7e8f901
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa


revision = "c6d7e8f901ab"
down_revision = "b5c6d7e8f901"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    # Trade motoru ayrımı: scalper vs agent. Mevcut pozisyonlar "agent" varsayılır.
    # Baseline create_all() model'den source'u zaten oluşturmuş olabilir → idempotent.
    if not _column_exists("portfolio_positions", "source"):
        op.add_column(
            "portfolio_positions",
            sa.Column("source", sa.String(), nullable=False, server_default="agent"),
        )


def downgrade() -> None:
    if _column_exists("portfolio_positions", "source"):
        op.drop_column("portfolio_positions", "source")