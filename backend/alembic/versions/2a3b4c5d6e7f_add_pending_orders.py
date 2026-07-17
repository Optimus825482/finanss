"""add pending_orders table

Revision ID: 2a3b4c5d6e7f
Revises: 1a2b3c4d5e6f
Create Date: 2026-07-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '2a3b4c5d6e7f'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pending_orders',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id'), index=True),
        sa.Column('ticker', sa.String(), index=True),
        sa.Column('action', sa.String()),
        sa.Column('quantity', sa.Float()),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text()),
        sa.Column('analysis_json', postgresql.JSON(), default={}),
        sa.Column('confidence', sa.Float(), default=0.7),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('exchange', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_index('ix_pending_orders_status', 'pending_orders', ['status'])
    op.create_index('ix_pending_orders_portfolio', 'pending_orders', ['portfolio_id'])


def downgrade() -> None:
    op.drop_table('pending_orders')
