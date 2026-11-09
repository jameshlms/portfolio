"""Web entry point: `uvicorn app.main:app` (Dockerfile) or `fastapi dev app/main.py`."""

from app.adapters.http.app import create_app
from app.bootstrap import bootstrap
from app.log_config import configure_logging

configure_logging()
app = create_app(bootstrap())
