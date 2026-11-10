"""Every business-rule error in the portfolio, grouped by feature.

Pure: no framework imports. The feature modules (services/blog.py, contact.py)
raise these for broken rules, and driven adapters translate infrastructure
failures into them. The edges (exception_handlers, the CLI) catch them and
translate, e.g. to an HTTP status or an exit code.
Everything here derives from `DomainError`, so a boundary can catch all of them
at once.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType


class DomainError(Exception):
    """Base for every business-rule error."""


def _describe(errors: Mapping[str, str]) -> str:
    return "; ".join(f"{field}: {reason}" for field, reason in errors.items())


# --- Contact form --------------------------------------------------------------


class ContactError(DomainError):
    """Base for everything that stops a contact message from being sent."""


class InvalidContactMessage(ContactError):
    """One or more fields break the message rules; `errors` maps field to reason."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        self.errors: Mapping[str, str] = MappingProxyType(dict(errors))
        super().__init__(_describe(errors))


class HumanCheckFailed(ContactError):
    """The visitor didn't pass the bot check."""


class HumanCheckUnavailable(ContactError):
    """The bot check couldn't be completed (the verification service is unreachable)."""


class DeliveryFailed(ContactError):
    """The message was valid but couldn't be delivered."""


# --- Blog ----------------------------------------------------------------------


class BlogError(DomainError):
    """Base for every blog rule violation."""


class InvalidPost(BlogError):
    """A post's file breaks the post rules; `errors` maps field to reason."""

    def __init__(self, slug: str, errors: Mapping[str, str]) -> None:
        self.slug = slug
        self.errors: Mapping[str, str] = MappingProxyType(dict(errors))
        super().__init__(f"{slug}: {_describe(errors)}")


class InvalidPosts(BlogError):
    """One or more posts are invalid; nothing was stored."""

    def __init__(self, posts: Sequence[InvalidPost]) -> None:
        self.posts: tuple[InvalidPost, ...] = tuple(posts)
        super().__init__("; ".join(str(p) for p in self.posts))


class PostsUnavailable(BlogError):
    """The posts can't be read or written right now (e.g. the store is unreachable)."""


class PostNotFound(BlogError):
    """No published post has this slug."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(slug)


class UnknownTag(BlogError):
    """No published post carries this tag."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        super().__init__(tag)
