"""add fair_value, margin_pct, valuation_assessment, llm fields to stock_picks

Revision ID: 1a2b3c4d5e6f
Revises: 9c1d5f7e3a2b
Create Date: 2026-07-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, None] = '9c1d5f7e3a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stock_picks', sa.Column('fair_value', sa.Float(), nullable=True))
    op.add_column('stock_picks', sa.Column('margin_pct', sa.Float(), nullable=True))
    op.add_column('stock_picks', sa.Column('valuation_assessment', sa.String(), nullable=True))
    op.add_column('stock_picks', sa.Column('llm_reasoning', sa.Text(), nullable=True))
    op.add_column('stock_picks', sa.Column('llm_target_price', sa.Float(), nullable=True))
    op.add_column('stock_picks', sa.Column('llm_expected_return_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('stock_picks', 'llm_expected_return_pct')
    op.drop_column('stock_picks', 'llm_target_price')
    op.drop_column('stock_picks', 'llm_reasoning')
    op.drop_column('stock_picks', 'valuation_assessment')
    op.drop_column('stock_picks', 'margin_pct')
    op.drop_column('stock_picks', 'fair_value')
