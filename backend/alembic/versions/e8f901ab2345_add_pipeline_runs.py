"""persist pipeline execution status"""
from alembic import op
import sqlalchemy as sa

revision = "e8f901ab2345"
down_revision = "d7e8f901ab23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("pipeline_runs"):
        op.create_table(
            "pipeline_runs",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("exchange", sa.String(length=20), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id"), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("progress", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("pipeline_runs"):
        op.drop_table("pipeline_runs")
