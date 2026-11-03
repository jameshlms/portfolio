from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.paths import Page
from app.services.seo.head import for_page
from app.templates import make_templates

_templates = make_templates()

router = APIRouter(default_response_class=HTMLResponse)


@router.get(Page.HOME)
async def home(request: Request):
    # Role cards aren't built yet (_role_card.html); the loop renders nothing until they are.
    return _templates.TemplateResponse(
        request, "pages/index.html", {"seo": for_page(Page.HOME), "roles": ()}
    )


@router.get(Page.ABOUT)
async def about(request: Request):
    return _templates.TemplateResponse(
        request, "pages/about.html", {"seo": for_page(Page.ABOUT)}
    )


@router.get(Page.CONTACT)
async def contact(request: Request):
    return _templates.TemplateResponse(
        request,
        "pages/contact.html",
        {
            "seo": for_page(Page.CONTACT),
            "contact_email": settings.contact_email,
            "linkedin_url": settings.linkedin_url,
        },
    )
