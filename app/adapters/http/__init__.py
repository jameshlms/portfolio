"""Driving adapter: the website (FastAPI, Jinja2 templates, htmx)."""

from pathlib import Path as _Path

HTTP_DIR = _Path(__file__).resolve().parent  # holds templates/ and static/
