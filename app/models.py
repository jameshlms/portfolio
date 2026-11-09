from datetime import datetime

from sqlalchemy import Index, String, Text, false, func
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BlogPost(Base):
    """Mirrors alembic revision 0001. Rows are written by `app.cli sync-posts`."""

    __tablename__ = "blog_posts"
    __table_args__ = (
        # Full-text search; search_vector is filled by a trigger (see migration 0001).
        Index("ix_blog_posts_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, server_default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    published_at: Mapped[datetime | None]  # None: draft
    revised_at: Mapped[datetime | None]  # the author's "updated" date
    content: Mapped[str] = mapped_column(Text)  # Markdown source; feeds search_vector
    content_html: Mapped[str] = mapped_column(Text)  # rendered at sync time
    has_charts: Mapped[bool] = mapped_column(server_default=false())  # load plotly.js
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
