"""The Container: which adapter fills each driven port, for one running process.

Built by app.bootstrap from settings (or by tests, from fakes) and handed to the
driving adapters: app.adapters.http.create_app and app.adapters.cli.main. It
holds ports, not concrete adapters, so nothing that receives it depends on
infrastructure.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.ports.driven.blog import MarkdownRenderer, PostRepositoryScope
from app.ports.driven.contact import HumanVerifier, MailSender


async def _nothing_to_close() -> None:
    return None


@dataclass(frozen=True)
class Container:
    posts: PostRepositoryScope
    renderer: MarkdownRenderer
    # None switches the contact form off: no bot check or no way to send mail.
    human_verifier: HumanVerifier | None = None
    mail_sender: MailSender | None = None
    # Releases what bootstrap opened (HTTP client, database pool). Call once, at shutdown.
    close: Callable[[], Awaitable[None]] = _nothing_to_close

    @property
    def can_send_contact_messages(self) -> bool:
        return self.human_verifier is not None and self.mail_sender is not None
