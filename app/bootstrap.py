"""Composition root: settings in, a Container of real adapters out.

The only module that knows which concrete adapter fills each port. app.main
(the website) and app.__main__ (the CLI) call `bootstrap()`; tests skip it and
build a Container of fakes.
"""

import httpx

from app.adapters.log_mail import LogMailSender
from app.adapters.markdown import MarkdownItRenderer
from app.adapters.memory_posts import InMemoryPostRepository, memory_post_repositories
from app.adapters.postgres.engine import make_engine, make_sessions
from app.adapters.postgres.posts import sql_post_repositories
from app.adapters.resend import ResendMailSender
from app.adapters.system_clock import SystemClock
from app.adapters.turnstile import TurnstileVerifier
from app.config import Settings
from app.config import settings as default_settings
from app.container import Container
from app.ports.driven.blog import PostRepositoryScope
from app.ports.driven.contact import HumanVerifier, MailSender


def bootstrap(settings: Settings = default_settings) -> Container:
    # One pooled client for outbound API calls (Turnstile, Resend).
    http = httpx.AsyncClient()

    posts: PostRepositoryScope
    if settings.database_url:
        engine = make_engine(settings.database_url)
        posts = sql_post_repositories(make_sessions(engine))
    else:
        # No database: the blog is empty and every other page still works.
        engine = None
        posts = memory_post_repositories(InMemoryPostRepository())

    async def close() -> None:
        await http.aclose()
        if engine is not None:
            await engine.dispose()

    return Container(
        posts=posts,
        renderer=MarkdownItRenderer(),
        clock=SystemClock(),
        posts_are_durable=engine is not None,
        human_verifier=_human_verifier(settings, http),
        mail_sender=_mail_sender(settings, http),
        close=close,
    )


def _human_verifier(
    settings: Settings, http: httpx.AsyncClient
) -> HumanVerifier | None:
    if not settings.turnstile_secret_key:
        return None
    return TurnstileVerifier(http, settings.turnstile_secret_key)


def _mail_sender(settings: Settings, http: httpx.AsyncClient) -> MailSender | None:
    if settings.resend_api_key:
        return ResendMailSender(
            http, settings.resend_api_key, settings.contact_from_email
        )
    if settings.debug:
        return LogMailSender()  # development: messages go to the log
    return None
