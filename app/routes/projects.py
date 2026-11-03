from pathlib import Path

from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from app.deps import IsHtmx
from app.templates import make_templates

templates = make_templates(Path(__file__).parent / "templates")

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_class=HTMLResponse)
async def projects(request: Request, htmx: IsHtmx):
    return templates.TemplateResponse(
        request=request,
        name="partials/project_grid.html" if htmx else "pages/project_list.html",
    )


@router.get("/{slug}")
async def project(request: Request, slug: str, htmx: IsHtmx):
    return templates.TemplateResponse(
        request=request,
    )
