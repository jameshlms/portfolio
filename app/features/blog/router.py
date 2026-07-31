from typing import Any

from fastapi import APIRouter, Request

from app.core import is_htmx
from app.features.blog.model import BlogPost
from app.shared.templates import templates

router = APIRouter(prefix="/blog", tags=["blog"])


def get_posts(tag: str | None = None, page: int = 1) -> tuple[list[BlogPost], bool]: ...


@router.get("")
def get_blogs(request: Request, tag: str | None = None, page: int = 1):
    posts, has_more = get_posts(tag=tag, page=page)
    context: dict[str, Any] = {
        "request": request,
        "posts": posts,
        "tag": tag,
        "page": page,
        "has_more": has_more,
    }
    return templates.TemplateResponse(
        "_post_list.html" if is_htmx(request) else "blogs.html",
        context,
    )


@router.get("/{blog_id}")
def get_blog(blog_id: int, request: Request): ...
