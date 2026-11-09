from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import StrictUndefined

from app.adapters.http import HTTP_DIR
from app.config import settings


def make_templates(*extra_dirs: Path) -> Jinja2Templates:
    t = Jinja2Templates(directory=[HTTP_DIR / "templates", *extra_dirs])
    t.env.globals["base_url"] = settings.base_url
    t.env.globals["site_name"] = settings.site_name
    t.env.undefined = StrictUndefined
    return t
