"""add italian text for posts

Revision ID: 0005_posts_it_text
Revises: 0004_posts_en_es_text
Create Date: 2026-04-17 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_posts_it_text"
down_revision = "0004_posts_en_es_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("tg_text_it", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "tg_text_it")
