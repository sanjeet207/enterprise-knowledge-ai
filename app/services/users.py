from dataclasses import dataclass
from typing import Optional, Tuple

import psycopg

from app.config import DATABASE_URL

_COLUMNS = "id, tenant_id, email, role_level, is_active"


@dataclass(frozen=True)
class User:
    id: str
    tenant_id: str
    email: str
    level: int
    is_active: bool


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def _to_user(row) -> User:
    return User(
        id=str(row[0]),
        tenant_id=row[1],
        email=row[2],
        level=row[3],
        is_active=row[4],
    )


def get_by_id(user_id: str) -> Optional[User]:
    with _connect() as conn:
        row = conn.execute(f"SELECT {_COLUMNS} FROM users WHERE id = %s", (user_id,)).fetchone()
    return _to_user(row) if row else None


def get_with_password_hash(email: str) -> Optional[Tuple[User, Optional[str]]]:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS}, password_hash FROM users WHERE lower(email) = lower(%s)",
            (email.strip(),),
        ).fetchone()
    return (_to_user(row), row[5]) if row else None


def is_engagement_member(engagement_id: str, user_id: str, tenant_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM engagement_members m JOIN engagements e ON e.id = m.engagement_id "
            "WHERE m.engagement_id = %s AND m.user_id = %s AND e.tenant_id = %s",
            (engagement_id, user_id, tenant_id),
        ).fetchone()
    return row is not None
