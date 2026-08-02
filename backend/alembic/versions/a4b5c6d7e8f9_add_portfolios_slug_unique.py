"""add unique constraint on portfolios.slug

Revision ID: a4b5c6d7e8f9
Revises: 3c4d5e6f7a8b
Create Date: 2026-08-02
"""
from alembic import op


revision = "a4b5c6d7e8f9"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_portfolios_slug", "portfolios", ["slug"])


def downgrade() -> None:
    op.drop_constraint("uq_portfolios_slug", "portfolios", type_="unique")
