"""Unit tests for Sahadan day-window math."""

from datetime import datetime

from tvsports_backend.fetch_sahadan import day_window
from tvsports_backend.fetch_sahadan import ISTANBUL


def test_today_window_is_yesterday_21_to_today_2059() -> None:
    now = datetime(2026, 9, 19, 15, 18, tzinfo=ISTANBUL)
    start, end, day = day_window(now, 0)
    assert day.day == 19
    assert start.day == 18
    assert start.hour == 21
    assert end.day == 19
    assert end.hour == 20
    assert end.minute == 59
