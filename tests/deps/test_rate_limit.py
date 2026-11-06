import pytest

from app.deps.rate_limit import Limit, RateLimiter


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_then_blocks() -> None:
    limiter = RateLimiter(Limit(count=2, seconds=60), clock=_Clock())

    assert [limiter.hit("ip") for _ in range(3)] == [True, True, False]


def test_window_slides() -> None:
    clock = _Clock()
    limiter = RateLimiter(Limit(count=1, seconds=60), clock=clock)

    assert limiter.hit("ip")
    clock.now = 59
    assert not limiter.hit("ip")
    clock.now = 60
    assert limiter.hit("ip")


def test_keys_are_independent() -> None:
    limiter = RateLimiter(Limit(count=1, seconds=60), clock=_Clock())

    assert limiter.hit("a")
    assert limiter.hit("b")


def test_every_limit_applies() -> None:
    clock = _Clock()
    limiter = RateLimiter(
        Limit(count=2, seconds=10), Limit(count=3, seconds=100), clock=clock
    )

    assert limiter.hit("ip") and limiter.hit("ip")
    clock.now = 10
    assert limiter.hit("ip")  # short window has reset
    clock.now = 20
    assert not limiter.hit("ip")  # but the long window is full


def test_blocked_attempts_are_not_counted() -> None:
    clock = _Clock()
    limiter = RateLimiter(Limit(count=1, seconds=60), clock=clock)

    limiter.hit("ip")
    for _ in range(5):
        limiter.hit("ip")
    clock.now = 60
    assert limiter.hit("ip")


def test_needs_a_limit() -> None:
    with pytest.raises(ValueError):
        RateLimiter()
