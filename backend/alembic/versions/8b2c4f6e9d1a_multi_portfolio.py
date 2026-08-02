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
    # Şema baseline create_all tarafından kurulur (model metadata). Bu migration
    # yalnızca eski DB'lerde (baseline öncesi elle kurulmuş) eksik tabloyu tamamlar:
    # IF NOT EXISTS ile idempotent. Kolonlar model'de mevcut olduğundan
    # add_column'lar atlanır (DuplicateColumn hata verir).
    conn = op.get_bind()
    has = conn.execute(
        sa.text("SELECT to_regclass('public.portfolios')")
    ).scalar() is not None
    if not has:
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

    # 2. portfolio_id FK'ler (nullable — null = legacy). Baseline create_all
    # model metadata'dan zaten eklediği için DuplicateColumn'u önlemek adına
    # varlık kontrolü yapıyoruz.
    conn = op.get_bind()
    insp = sa.inspect(conn)
    for tbl in ("portfolio_positions", "trading_decisions", "balance_transactions"):
        cols = {c["name"] for c in insp.get_columns(tbl)}
        if "portfolio_id" not in cols:
            op.add_column(
                tbl,
                sa.Column("portfolio_id", sa.Integer(), nullable=True, index=True),
            )
    if "fk_portfolio_positions_portfolio" not in {c["name"] for c in insp.get_foreign_keys("portfolio_positions")}:
        op.create_foreign_key(
            "fk_portfolio_positions_portfolio", "portfolio_positions", "portfolios",
            ["portfolio_id"], ["id"],
        )
    if "fk_trading_decisions_portfolio" not in {c["name"] for c in insp.get_foreign_keys("trading_decisions")}:
        op.create_foreign_key(
            "fk_trading_decisions_portfolio", "trading_decisions", "portfolios",
            ["portfolio_id"], ["id"],
        )
    if "fk_balance_transactions_portfolio" not in {c["name"] for c in insp.get_foreign_keys("balance_transactions")}:
        op.create_foreign_key(
            "fk_balance_transactions_portfolio", "balance_transactions", "portfolios",
            ["portfolio_id"], ["id"],
        )

    # 3. Seed: BIST + US portföyleri (mevcut slug'ları atla — idempotent)
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
    existing = {
        row[0]
        for row in conn.execute(sa.text("SELECT slug FROM portfolios")).fetchall()
    }
    rows = [
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
    ]
    rows = [r for r in rows if r["slug"] not in existing]
    if rows:
        op.bulk_insert(portfolios_table, rows)


def downgrade() -> None:
    op.drop_constraint("fk_balance_transactions_portfolio", "balance_transactions", type_="foreignkey")
    op.drop_constraint("fk_trading_decisions_portfolio", "trading_decisions", type_="foreignkey")
    op.drop_constraint("fk_portfolio_positions_portfolio", "portfolio_positions", type_="foreignkey")
    op.drop_column("balance_transactions", "portfolio_id")
    op.drop_column("trading_decisions", "portfolio_id")
    op.drop_column("portfolio_positions", "portfolio_id")
    op.drop_table("portfolios")
