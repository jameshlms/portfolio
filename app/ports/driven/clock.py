"""The current time, as the use cases see it (e.g. whether a post is published yet)."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """The current moment, timezone-aware."""
        ...
