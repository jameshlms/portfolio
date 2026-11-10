from datetime import UTC, datetime

from app.adapters.system_clock import SystemClock


def test_now_is_the_current_time_in_utc() -> None:
    before = datetime.now(UTC)

    now = SystemClock().now()

    assert now.tzinfo is UTC
    assert before <= now <= datetime.now(UTC)
