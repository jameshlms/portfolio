"""create blog_posts table

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blog_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("tags", ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column(
            "has_charts", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
    )

    op.create_index("ix_blog_posts_slug", "blog_posts", ["slug"], unique=True)
    op.create_index(
        "ix_blog_posts_search_vector",
        "blog_posts",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION blog_posts_tsv_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.summary, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(array_to_string(NEW.tags, ' '), '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.content, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER blog_posts_tsv_trigger
        BEFORE INSERT OR UPDATE ON blog_posts
        FOR EACH ROW EXECUTE FUNCTION blog_posts_tsv_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS blog_posts_tsv_trigger ON blog_posts;")
    op.execute("DROP FUNCTION IF EXISTS blog_posts_tsv_update;")
    op.drop_table("blog_posts")
