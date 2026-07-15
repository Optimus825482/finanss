"""initial_baseline — create all tables from current models (idempotent)

Uses Base.metadata.create_all() which is internally CREATE TABLE IF NOT EXISTS,
so it works whether tables already exist from a previous init_db() run or not.

NOTE: create_all only adds tables that don't exist yet — it does NOT detect
schema drift (added/removed/dropped columns) on existing tables. For any model
change after this baseline, generate a real migration with
`alembic revision --autogenerate -m "describe change"` and use op.add_column /
op.drop_column etc. Do NOT just re-run this baseline.

Revision ID: 52c8062ed019
Revises:
Create Date: 2026-07-08 16:20:54.103324
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "52c8062ed019"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables idempotently using SQLAlchemy metadata.

    Models are already imported in env.py → Base.metadata is populated.
    create_all() checks `IF NOT EXISTS` internally, safe to run repeatedly.
    """
    from app.database import Base

    bind = op.get_bind()

    # Enable pgvector extension (IF NOT EXISTS is idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create all tables that don't exist yet
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop all tables managed by this metadata."""
    from app.database import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
