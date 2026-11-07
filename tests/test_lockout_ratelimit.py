import datetime as dt

from app.services import lockout
from app.services.ratelimit import SlidingWindow

NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)


def test_not_locked_without_a_lock_time():
    assert not lockout.is_locked(None, NOW)


def test_locked_until_the_time_passes():
    until = NOW + dt.timedelta(minutes=lockout.LOCK_MINUTES)
    assert lockout.is_locked(until, NOW)
    assert not lockout.is_locked(until, until + dt.timedelta(seconds=1))


def test_lockout_settings_are_sensible():
    assert 3 <= lockout.MAX_FAILURES <= 10 and lockout.LOCK_MINUTES >= 5


def test_window_allows_up_to_the_limit_then_blocks():
    w = SlidingWindow(3, 60)
    assert [w.allow("a", t) for t in (0, 1, 2)] == [True, True, True]
    assert w.allow("a", 3) is False


def test_window_frees_up_after_it_slides():
    w = SlidingWindow(2, 60)
    w.allow("a", 0); w.allow("a", 10)
    assert w.allow("a", 30) is False
    assert w.allow("a", 61) is True


def test_people_are_limited_separately():
    w = SlidingWindow(1, 60)
    assert w.allow("a", 0) and w.allow("b", 0)
    assert not w.allow("a", 1)
