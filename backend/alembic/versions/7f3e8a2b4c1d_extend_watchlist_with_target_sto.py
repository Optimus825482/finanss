"""extend watchlist with target/stop/signal

stock_analysis skill entegrasyonu: alert/stop/signal takibi için WatchlistItem
tablosuna 4 kolon ekler.

Revision ID: 7f3e8a2b4c1d
Revises: 52c8062ed019
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f3e8a2b4c1d"
down_revision = "52c8062ed019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # alert_on_signal için server_default true — mevcut satırlar true kabul edilir
    op.add_column(
        "watchlist_items",
        sa.Column("target_price", sa.Float(), nullable=True),
    )
    op.add_column(
        "watchlist_items",
        sa.Column("stop_price", sa.Float(), nullable=True),
    )
    op.add_column(
        "watchlist_items",
        sa.Column(
            "alert_on_signal",
            sa.Boolean(),
            nullable=True,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "watchlist_items",
        sa.Column("last_signal", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watchlist_items", "last_signal")
    op.drop_column("watchlist_items", "alert_on_signal")
    op.drop_column("watchlist_items", "stop_price")
    op.drop_column("watchlist_items", "target_price")
