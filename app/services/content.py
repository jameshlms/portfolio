# Project, ProjectRead, ProjectSummary and Kind don't exist yet; drop both lines once they do.
# ruff: noqa: F821
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import paths
from app.models import BlogPost
from app.services.seo import EntityDetails, Listing


async def get_project(db: AsyncSession, slug: str) -> ProjectRead | None:
    row = await db.scalar(
        select(Project)
        .where(Project.slug == slug, Project.published.is_(True))
        .options(selectinload(Project.media), selectinload(Project.tags)))
    return ProjectRead.model_validate(row) if row else None

async def list_projects(db: AsyncSession, kind: Kind | None = None) -> list[ProjectSummary]:
    stmt = select(Project).where(Project.published.is_(True)).order_by(Project.updated_at.desc())
    if kind:
        stmt = stmt.where(Project.kind == kind)
    rows = (await db.scalars(stmt.options(selectinload(Project.tags), selectinload(Project.cover)))).all()
    return [ProjectSummary.model_validate(r) for r in rows]


async def published_for_sitemap(db: AsyncSession) -> tuple[EntityDetails, ...]:
    rows = await db.execute(
        select(BlogPost.slug, BlogPost.updated_at)
        .where(BlogPost.published_at.is_not(None))
        .order_by(BlogPost.published_at.desc())
    )
    return tuple(
        EntityDetails(paths.entity_path(paths.Page.BLOG, slug), updated_at)
        for slug, updated_at in rows
    )


async def published_post_listings(db: AsyncSession) -> tuple[Listing, ...]:
    rows = await db.execute(
        select(BlogPost.slug, BlogPost.title, BlogPost.summary)
        .where(BlogPost.published_at.is_not(None))
        .order_by(BlogPost.published_at.desc())
    )
    return tuple(
        Listing(paths.entity_path(paths.Page.BLOG, slug), title, summary)
        for slug, title, summary in rows
    )
