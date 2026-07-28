from typing import Any

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.core import is_htmx
from app.features import BlogPost

router = APIRouter("api")
templates = Jinja2Templates(directory="app/features/blog/templates")


def get_posts(tag: str | None = None, page: int = 1) -> tuple[list[BlogPost], bool]: ...


@router.get("blogs")
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
        "partials/_post_list.html" if is_htmx(request) else "blogs.html",
        context,
    )


@router.get("blogs/{blog_id}")
def get_blog(blog_id: int, request: Request): ...
