"""multi-portfolio — portfolios table + portfolio_id FK on positions/decisions/transactions + seed

Çoklu portföy yönetimi (BIST + US). Yeni portfolios tablosu + mevcut
tablolara portfolio_id nullable FK. Seed: 2 Portfolio kaydı (bist, us).

Revision ID: 8b2c4f6e9d1a
Revises: 7f3e8a2b4c1d
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa


revision = "8b2c4f6e9d1a"
down_revision = "7f3e8a2b4c1d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. portfolios tablosu
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("slug", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("exchanges", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("cash", sa.Float(), nullable=False, server_default="10000.0"),
        sa.Column("max_positions", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("max_per_position_pct", sa.Float(), nullable=False, server_default="0.25"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # 2. portfolio_id FK'ler (nullable — null = legacy)
    op.add_column(
        "portfolio_positions",
        sa.Column("portfolio_id", sa.Integer(), nullable=True, index=True),
    )
    op.add_column(
        "trading_decisions",
        sa.Column("portfolio_id", sa.Integer(), nullable=True, index=True),
    )
    op.add_column(
        "balance_transactions",
        sa.Column("portfolio_id", sa.Integer(), nullable=True, index=True),
    )
    op.create_foreign_key(
        "fk_portfolio_positions_portfolio", "portfolio_positions", "portfolios",
        ["portfolio_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_trading_decisions_portfolio", "trading_decisions", "portfolios",
        ["portfolio_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_balance_transactions_portfolio", "balance_transactions", "portfolios",
        ["portfolio_id"], ["id"],
    )

    # 3. Seed: BIST + US portföyleri
    portfolios_table = sa.table(
        "portfolios",
        sa.column("slug", sa.String),
        sa.column("display_name", sa.String),
        sa.column("exchanges", sa.JSON),
        sa.column("cash", sa.Float),
        sa.column("max_positions", sa.Integer),
        sa.column("max_per_position_pct", sa.Float),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    from datetime import datetime
    now = datetime.utcnow()
    op.bulk_insert(portfolios_table, [
        {
            "slug": "bist",
            "display_name": "BIST Portföyü",
            "exchanges": ["BIST"],
            "cash": 10000.0,
            "max_positions": 8,
            "max_per_position_pct": 0.25,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "slug": "us",
            "display_name": "US Portföyü (NASDAQ+DJIA)",
            "exchanges": ["NASDAQ", "DOWJONES"],
            "cash": 10000.0,
            "max_positions": 8,
            "max_per_position_pct": 0.25,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ])


def downgrade() -> None:
    op.drop_constraint("fk_balance_transactions_portfolio", "balance_transactions", type_="foreignkey")
    op.drop_constraint("fk_trading_decisions_portfolio", "trading_decisions", type_="foreignkey")
    op.drop_constraint("fk_portfolio_positions_portfolio", "portfolio_positions", type_="foreignkey")
    op.drop_column("balance_transactions", "portfolio_id")
    op.drop_column("trading_decisions", "portfolio_id")
    op.drop_column("portfolio_positions", "portfolio_id")
    op.drop_table("portfolios")
