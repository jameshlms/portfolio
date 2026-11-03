from pathlib import Path as _Path

from app.config import settings

APP_DIR = _Path(__file__).resolve().parent

__all__ = ["APP_DIR", "settings"]
