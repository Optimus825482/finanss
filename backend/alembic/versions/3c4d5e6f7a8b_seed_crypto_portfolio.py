"""seed crypto portfolio + scraping settings

Crypto portföyü (Binance M5) — portfolios tablosuna seed + scraping
ayarları için varsayılan SystemSettings satırları (yoksa).

Revision ID: 3c4d5e6f7a8b
Revises: 2a3b4c5d6e7f
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, None] = '2a3b4c5d6e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from datetime import datetime
    now = datetime.utcnow()

    # 1. Crypto portföyü seed — portfolios tablosuna (yoksa)
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
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT slug FROM portfolios WHERE slug = 'crypto'")
    ).fetchone()
    if existing is None:
        op.bulk_insert(portfolios_table, [
            {
                "slug": "crypto",
                "display_name": "Kripto Portföyü (Binance)",
                "exchanges": ["CRYPTO"],
                "cash": 5000.0,
                "max_positions": 6,
                "max_per_position_pct": 0.30,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        ])

    # 2. Scraping ayarları varsayılanları — SystemSettings tablosuna (yoksa)
    settings_table = sa.table(
        "system_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
        sa.column("description", sa.String),
        sa.column("updated_at", sa.DateTime),
    )
    for key, value, desc in [
        ("scraping_enabled", "1", "Global otonom scraping aç/kapat"),
        ("scraping_bist", "1", "BIST otonom scraping aç/kapat"),
        ("scraping_us", "1", "US otonom scraping aç/kapat"),
        ("scraping_crypto", "1", "Kripto otonom scraping aç/kapat"),
    ]:
        exists = conn.execute(
            sa.text("SELECT key FROM system_settings WHERE key = :k"),
            {"k": key},
        ).fetchone()
        if exists is None:
            op.bulk_insert(settings_table, [
                {"key": key, "value": value, "description": desc, "updated_at": now},
            ])


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM portfolios WHERE slug = 'crypto'"))
    conn.execute(
        sa.text("DELETE FROM system_settings WHERE key LIKE 'scraping_%'")
    )
