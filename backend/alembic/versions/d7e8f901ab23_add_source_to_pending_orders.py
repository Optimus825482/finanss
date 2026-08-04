"""add trade engine source to pending orders"""
from alembic import op
import sqlalchemy as sa

revision = "d7e8f901ab23"
down_revision = "c6d7e8f901ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not any(c["name"] == "source" for c in inspector.get_columns("pending_orders")):
        op.add_column("pending_orders", sa.Column("source", sa.String(), nullable=False, server_default="agent"))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if any(c["name"] == "source" for c in inspector.get_columns("pending_orders")):
        op.drop_column("pending_orders", "source")
