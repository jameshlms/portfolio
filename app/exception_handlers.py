from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.services import seo
from app.templates import make_templates

_templates = make_templates()


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
        )

    if exc.status_code == 404:
        template = "errors/404.html"
        page = seo.for_error_page(
            "Page not found",
            "The page you're looking for doesn't exist.",
            request.url.path,
        )
    else:
        template = "errors/500.html"
        page = seo.for_error_page(
            "Something went wrong", "An unexpected error occurred.", request.url.path
        )

    return _templates.TemplateResponse(
        request,
        template,
        {"seo": page, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )


type ExceptionHandler = Callable[[Request, Any], Coroutine[Any, Any, Response]]

# Annotated with FastAPI's parameter type: dict is invariant, so the inferred
# dict[type[HTTPException], ...] wouldn't be accepted.
exception_handlers: dict[int | type[Exception], ExceptionHandler] = {
    HTTPException: http_exception_handler
}
