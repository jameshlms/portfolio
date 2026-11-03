from fastapi import APIRouter, Request

from app.paths import Reserved
from app.services.seo import llms_document, sitemap_entries
from app.templates import make_templates

_templates = make_templates()

_CACHE_HEADERS = {"Cache-Control": "public, max-age=3600"}


router = APIRouter(include_in_schema=False)


@router.get(Reserved.SITEMAP)
async def sitemap(request: Request):
    # Blog posts join via content.published_for_sitemap once /blog/{slug} has a route.
    return _templates.TemplateResponse(
        request,
        "seo/sitemap.xml.j2",
        context={"entries": sitemap_entries()},
        media_type="application/xml",
        headers=_CACHE_HEADERS,
    )


@router.get(Reserved.ROBOTS)
async def robots(request: Request):
    return _templates.TemplateResponse(
        request,
        "seo/robots.txt.j2",
        context={"disallow": (Reserved.ADMIN,), "sitemap_path": Reserved.SITEMAP},
        media_type="text/plain",
        headers=_CACHE_HEADERS,
    )


@router.get(Reserved.LLMS)
async def llms(request: Request):
    # Blog posts join via content.published_post_listings once /blog/{slug} has a route.
    return _templates.TemplateResponse(
        request,
        "seo/llms.txt.j2",
        context={"doc": llms_document(())},
        media_type="text/plain",
        headers=_CACHE_HEADERS,
    )
