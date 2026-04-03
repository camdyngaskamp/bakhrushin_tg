"""init

Revision ID: 0001_init
Revises: 
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("type", sa.Enum("rss","html", name="sourcetype"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("parser_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("hash_text", sa.String(length=64), nullable=True),
        sa.Column("lang", sa.String(length=16), nullable=True),
        sa.Column("status", sa.Enum("new","ai_ready","rejected", name="itemstatus"), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("url", name="uq_items_url"),
    )
    op.create_index("ix_items_hash_text", "items", ["hash_text"])

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("tg_text", sa.Text(), nullable=True),
        sa.Column("tg_media", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("style_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("moderation_status", sa.Enum("pending","approved","rejected","scheduled","posted","failed", name="moderationstatus"), nullable=False, server_default="pending"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tg_message_id", sa.String(length=64), nullable=True),
        sa.Column("editor_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

def downgrade():
    op.drop_table("posts")
    op.drop_index("ix_items_hash_text", table_name="items")
    op.drop_table("items")
    op.drop_table("sources")
    op.execute("DROP TYPE IF EXISTS moderationstatus")
    op.execute("DROP TYPE IF EXISTS itemstatus")
    op.execute("DROP TYPE IF EXISTS sourcetype")
