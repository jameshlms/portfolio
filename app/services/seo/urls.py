from app.config import settings


def absolute_url(path: str) -> str:
    return f"{settings.base_url}/{path.removeprefix('/')}"


def absolute_asset_url(url: str) -> str:
    """Assets may live on another host (CDN); only site-relative paths are resolved."""
    return url if "://" in url else absolute_url(url)
