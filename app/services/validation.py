"""Plain input checks for the admin screens. No database, so they are easy to test."""
import re

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
