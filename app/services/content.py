# Project, ProjectRead, ProjectSummary and Kind don't exist yet; drop both lines once they do.
# ruff: noqa: F821
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import paths
from app.models import BlogPost
from app.services.seo.page_meta import PublishedPage


async def get_project(db: AsyncSession, slug: str) -> ProjectRead | None:
    row = await db.scalar(
        select(Project)
        .where(Project.slug == slug, Project.published.is_(True))
        .options(selectinload(Project.media), selectinload(Project.tags))
    )
    return ProjectRead.model_validate(row) if row else None


async def list_projects(
    db: AsyncSession, kind: Kind | None = None
) -> list[ProjectSummary]:
    stmt = (
        select(Project)
        .where(Project.published.is_(True))
        .order_by(Project.updated_at.desc())
    )
    if kind:
        stmt = stmt.where(Project.kind == kind)
    rows = (
        await db.scalars(
            stmt.options(selectinload(Project.tags), selectinload(Project.cover))
        )
    ).all()
    return [ProjectSummary.model_validate(r) for r in rows]


async def published_posts(db: AsyncSession) -> tuple[PublishedPage, ...]:
    """Published blog posts, newest first; feeds the sitemap and llms.txt."""
    rows = await db.execute(
        select(BlogPost.slug, BlogPost.title, BlogPost.summary, BlogPost.updated_at)
        .where(BlogPost.published_at.is_not(None))
        .order_by(BlogPost.published_at.desc())
    )
    return tuple(
        PublishedPage(
            path=paths.item_path(paths.Page.BLOG, slug),
            title=title,
            summary=summary,
            last_modified=updated_at,
        )
        for slug, title, summary, updated_at in rows
    )
