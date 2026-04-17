import enum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class SourceType(str, enum.Enum):
    rss = "rss"
    html = "html"

class ItemStatus(str, enum.Enum):
    new = "new"
    ai_ready = "ai_ready"
    rejected = "rejected"

class ModerationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    scheduled = "scheduled"
    posted = "posted"
    failed = "failed"

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    type = Column(Enum(SourceType), nullable=False)
    url = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    parser_config = Column(JSONB, nullable=False, default=dict)


    last_status_code = Column(Integer, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    fail_streak = Column(Integer, nullable=False, server_default="0")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("Item", back_populates="source")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)

    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)

    raw_text = Column(Text, nullable=True)
    raw_html = Column(Text, nullable=True)

    hash_text = Column(String(64), nullable=True, index=True)
    lang = Column(String(16), nullable=True)

    status = Column(Enum(ItemStatus), nullable=False, default=ItemStatus.new)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source = relationship("Source", back_populates="items")
    post = relationship("Post", back_populates="item", uselist=False)

    __table_args__ = (UniqueConstraint("url", name="uq_items_url"),)

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, unique=True)

    tg_text = Column(Text, nullable=True)
    tg_text_th = Column(Text, nullable=True)  # Thai text for publication
    tg_text_en = Column(Text, nullable=True)  # English text for publication
    tg_text_es = Column(Text, nullable=True)  # Spanish text for publication
    tg_text_it = Column(Text, nullable=True)  # Italian text for publication
    tg_media = Column(JSONB, nullable=False, default=dict)

    style_version = Column(String(32), nullable=False, default="v1")

    moderation_status = Column(Enum(ModerationStatus), nullable=False, default=ModerationStatus.pending)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    tg_message_id = Column(String(64), nullable=True)
    editor_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item", back_populates="post")
