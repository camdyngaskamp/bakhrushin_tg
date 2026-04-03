"""sources health fields

Revision ID: 0002_sources_health
Revises: 0001_init
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_sources_health"
down_revision = "0001_init"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sources", sa.Column("last_status_code", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("fail_streak", sa.Integer(), nullable=False, server_default=sa.text('0')))

def downgrade():
    op.drop_column("sources", "last_error")
    op.drop_column("sources", "last_checked_at")
    op.drop_column("sources", "last_status_code")
    op.drop_column("sources", "fail_streak")
