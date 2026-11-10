from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.adapters.http.paths import Page
from app.adapters.http.presentation import seo
from app.adapters.http.templates import make_templates
from app.config import settings

_templates = make_templates()

router = APIRouter(default_response_class=HTMLResponse)


@router.get(Page.HOME)
async def home(request: Request):
    return _templates.TemplateResponse(
        request, "pages/index.html", {"seo": seo.for_page(Page.HOME)}
    )


@router.get(Page.ABOUT)
async def about(request: Request):
    return _templates.TemplateResponse(
        request, "pages/about.html", {"seo": seo.for_page(Page.ABOUT)}
    )


@router.get(Page.RESUME, response_class=RedirectResponse)
async def resume(request: Request) -> RedirectResponse:
    """Stable link to the résumé, wherever it's hosted (RESUME_URL).

    A placeholder until the résumé is published: with RESUME_URL unset it sends
    visitors to the About page. 307 because the target is expected to change.
    """
    target = settings.resume_url or str(request.url_for("about"))
    return RedirectResponse(target, status_code=307)
