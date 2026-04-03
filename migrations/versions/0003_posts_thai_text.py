"""add thai text for posts

Revision ID: 0003_posts_thai_text
Revises: 0002_sources_health
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_posts_thai_text"
down_revision = "0002_sources_health"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("posts", sa.Column("tg_text_th", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("posts", "tg_text_th")
