"""Sign-in lockout rule. A locked account looks exactly like a wrong password from the outside."""
import datetime as dt
from typing import Optional

MAX_FAILURES = 5
LOCK_MINUTES = 15


def is_locked(locked_until: Optional[dt.datetime], now: Optional[dt.datetime] = None) -> bool:
    now = now or dt.datetime.now(dt.timezone.utc)
    return locked_until is not None and locked_until > now
