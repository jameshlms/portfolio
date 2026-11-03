from fastapi import APIRouter, Request

from app.paths import Internal, RootFile
from app.services.seo import llms_document, sitemap_urls
from app.templates import make_templates

_templates = make_templates()

_CACHE_HEADERS = {"Cache-Control": "public, max-age=3600"}


router = APIRouter(include_in_schema=False)


@router.get(RootFile.SITEMAP)
async def sitemap(request: Request):
    # Blog posts join via content.published_posts once /blog/{slug} has a route.
    return _templates.TemplateResponse(
        request,
        "seo/sitemap.xml.j2",
        context={"urls": sitemap_urls()},
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
async def llms(request: Request):
    # Blog posts join via content.published_posts once /blog/{slug} has a route.
    return _templates.TemplateResponse(
        request,
        "seo/llms.txt.j2",
        context={"doc": llms_document(())},
        media_type="text/plain",
        headers=_CACHE_HEADERS,
    )
