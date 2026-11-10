import os
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit

from pydantic import BeforeValidator, HttpUrl, TypeAdapter
from pydantic_settings import BaseSettings, SettingsConfigDict

_DatabaseUrl = Annotated[
    str,
    BeforeValidator(lambda v: str(v).replace("postgresql://", "postgresql+asyncpg://")),
]

_http = TypeAdapter(HttpUrl)


def _clean_url(v: object) -> str:
    s = str(v).strip()
    if "://" not in s:
        s = f"https://{s}"
    u = urlsplit(str(_http.validate_python(s)))
    return urlunsplit(
        (u.scheme, u.netloc, u.path.rstrip("/"), u.query, "")
    )  # drop fragment, trailing slash


WebUrl = Annotated[str, BeforeValidator(_clean_url)]


class Settings(BaseSettings):
    base_url: WebUrl = "https://jameshlms.com"
    site_name: str = "James Holmes"
    linkedin_url: WebUrl = "https://www.linkedin.com/in/jameshlms/"
    github_url: WebUrl = "https://github.com/jameshlms"
    contact_email: str = "j.r.holmes@outlook.com"
    gravatar_url: WebUrl | None = "https://gravatar.com/hardrebel709a4b15c2"
    # Contact form: shown once Turnstile is configured and mail can be sent (Resend,
    # or logged in debug). contact_from_email's domain must be verified in Resend.
    resend_api_key: str | None = None
    contact_from_email: str = "Portfolio contact <contact@jameshlms.com>"
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None
    # Where /resume redirects (e.g. a CDN-hosted PDF). Unset, it falls back to the About page.
    resume_url: WebUrl | None = None
    allowed_hosts: list[str] = [
        "jameshlms.com",
        "jameshlms.github.io",
        "www.jameshlms.com",
        "*.railway.app",
        "localhost",
        "127.0.0.1",
        "admin.jameshlms.com",
    ]
    debug: bool = False
    database_url: _DatabaseUrl | None = None

    model_config = SettingsConfigDict(
        # PORTFOLIO_ENV_FILE picks the dotenv file; empty reads none (the tests set it,
        # so they never depend on a developer's .env). Environment variables always apply.
        env_file=os.environ.get("PORTFOLIO_ENV_FILE", ".env") or None,
        env_file_encoding="utf-8",
        # A bad setting is reported by name, never by value: these errors reach test
        # output and deploy logs, and the values are often secrets.
        hide_input_in_errors=True,
    )

    @property
    def contact_form_enabled(self) -> bool:
        has_mail = bool(self.resend_api_key) or self.debug
        return bool(self.turnstile_site_key and self.turnstile_secret_key) and has_mail


settings = Settings()
