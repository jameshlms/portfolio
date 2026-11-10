from fastapi import APIRouter, Request

from app.adapters.http.deps import AppClock
from app.adapters.http.deps.blog import Posts
from app.adapters.http.paths import Internal, RootFile
from app.adapters.http.presentation.seo import (
    llms_document,
    published_posts,
    sitemap_urls,
)
from app.adapters.http.templates import make_templates
from app.services.blog import list_published_posts

_templates = make_templates()

_CACHE_HEADERS = {"Cache-Control": "public, max-age=3600"}


router = APIRouter(include_in_schema=False)


@router.get(RootFile.SITEMAP)
async def sitemap(request: Request, posts: Posts, clock: AppClock):
    blog = published_posts(await list_published_posts(posts, clock))
    return _templates.TemplateResponse(
        request,
        "seo/sitemap.xml.j2",
        context={"urls": sitemap_urls(blog)},
        media_type="application/xml",
        headers=_CACHE_HEADERS,
    )


@router.get(RootFile.ROBOTS)
async def robots(request: Request):
    return _templates.TemplateResponse(
        request,
        "seo/robots.txt.j2",
        context={"disallow": (Internal.ADMIN,), "sitemap_path": RootFile.SITEMAP},
        media_type="text/plain",
        headers=_CACHE_HEADERS,
    )


@router.get(RootFile.LLMS)
async def llms(request: Request, posts: Posts, clock: AppClock):
    blog = published_posts(await list_published_posts(posts, clock))
    return _templates.TemplateResponse(
        request,
        "seo/llms.txt.j2",
        context={"doc": llms_document(blog)},
        media_type="text/plain",
        headers=_CACHE_HEADERS,
    )
