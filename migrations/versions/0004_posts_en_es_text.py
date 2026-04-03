"""add english and spanish post texts

Revision ID: 0004_posts_en_es_text
Revises: 0003_posts_thai_text
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_posts_en_es_text"
down_revision = "0003_posts_thai_text"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("posts", sa.Column("tg_text_en", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("tg_text_es", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("posts", "tg_text_es")
    op.drop_column("posts", "tg_text_en")
