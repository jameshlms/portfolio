from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings

_app_dir = Path(__file__).parent.parent
_template_dirs = [_app_dir / "templates"] + sorted(_app_dir.glob("features/*/templates"))

templates = Jinja2Templates(directory=_template_dirs)
templates.env.globals["base_url"] = settings.base_url
