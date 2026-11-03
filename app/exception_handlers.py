from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.templates import make_templates

_templates = make_templates()


class DomainException(Exception):
    def __init__(self, message: str, detail: dict[str, str]):
        self.detail = detail
        super().__init__(message)


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
        )

    template = "errors/404.html" if exc.status_code == 404 else "errors/500.html"
    return _templates.TemplateResponse(
        request,
        template,
        {"status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )


exception_handlers = {HTTPException: http_exception_handler}
