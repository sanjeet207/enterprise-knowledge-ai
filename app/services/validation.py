"""Plain input checks for the admin screens. No database, so they are easy to test."""
import datetime as dt
import re
from typing import Optional

EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
MIN_PASSWORD = 10


def clean_email(value: str) -> str:
    email = (value or "").strip().lower()
    if len(email) > 254 or not EMAIL.match(email):
        raise ValueError("Enter a valid email address")
    return email


def check_password(value: str) -> str:
    if len(value or "") < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters")
    if len(value) > 128:
        raise ValueError("Password is too long")
    return value


def check_level(value: int) -> int:
    if value not in (1, 2, 3, 4):
        raise ValueError("Level must be 1 to 4")
    return value


def check_review_date(value: str, today: Optional[dt.date] = None) -> Optional[str]:
    """A date (YYYY-MM-DD) by which the document must be reviewed, or None. Must be in the future, within 5 years."""
    value = (value or "").strip()
    if not value:
        return None
    today = today or dt.date.today()
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("Review date must look like 2027-06-30")
    if day <= today:
        raise ValueError("Review date must be in the future")
    if day > today + dt.timedelta(days=1826):
        raise ValueError("Review date is too far away (5 years at most)")
    return day.isoformat()
