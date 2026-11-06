"""A small in-memory, sliding-window rate limiter for form posts.

Per process, which is fine for one Railway replica. If the app ever runs more
than one, move the counts to Redis (REDIS_URL is already a setting).
"""

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    count: int
    seconds: float


class RateLimiter:
    _SWEEP_AT = 10_000  # keys tracked before idle ones are dropped

    def __init__(
        self, *limits: Limit, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if not limits:
            raise ValueError("RateLimiter needs at least one Limit")
        self._limits = limits
        self._horizon = max(limit.seconds for limit in limits)
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        """Record an attempt for `key`; False (and not recorded) if it's over any limit."""
        now = self._clock()
        if len(self._hits) >= self._SWEEP_AT:
            self._sweep(now)

        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._horizon:
            hits.popleft()
        for limit in self._limits:
            if sum(1 for t in hits if now - t < limit.seconds) >= limit.count:
                return False
        hits.append(now)
        return True

    def _sweep(self, now: float) -> None:
        self._hits = {
            key: hits
            for key, hits in self._hits.items()
            if hits and now - hits[-1] < self._horizon
        }
