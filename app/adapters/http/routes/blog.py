"""Blog index (optionally filtered by tag) and post pages.

The tag links on the index use htmx to swap just the post list; htmx requests
get the list fragment, everything else (plain links, history restores) the page.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app.adapters.http.deps import AppClock, IsHtmx
from app.adapters.http.deps.blog import Posts
from app.adapters.http.paths import Page, item_path
from app.adapters.http.presentation import seo
from app.adapters.http.templates import make_templates
from app.domain.errors import PostNotFound, UnknownTag
from app.services.blog import blog_index, get_post

_templates = make_templates()

router = APIRouter(tags=["blog"], default_response_class=HTMLResponse)


@router.get(Page.BLOG)
async def blog(
    request: Request,
    posts: Posts,
    clock: AppClock,
    htmx: IsHtmx,
    tag: str | None = None,
) -> Response:
    try:
        index = await blog_index(posts, clock, tag or None)
    except UnknownTag as e:
        raise HTTPException(status_code=404) from e

    context = {"index": index, "seo": seo.for_blog_index(index.tag), "htmx": htmx}
    template = "components/_post_list.html" if htmx else "pages/blog.html"
    return _templates.TemplateResponse(request, template, context)


@router.get(item_path(Page.BLOG, "{slug}"))
async def blog_post(
    request: Request, posts: Posts, clock: AppClock, slug: str
) -> Response:
    try:
        post = await get_post(posts, clock, slug)
    except PostNotFound as e:
        raise HTTPException(status_code=404) from e

    return _templates.TemplateResponse(
        request, "pages/blog_post.html", {"post": post, "seo": seo.for_post(post)}
    )
