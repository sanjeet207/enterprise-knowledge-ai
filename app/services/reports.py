"""Saved research reports. Private to the person who asked for them."""
import uuid
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.types.json import Jsonb

from app.config import DATABASE_URL
from app.services.users import User


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def save(user: User, request: str, report: Dict[str, Any]) -> str:
    report_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute("INSERT INTO research_reports (id, tenant_id, user_id, request, report) VALUES (%s,%s,%s,%s,%s)",
                     (report_id, user.tenant_id, user.id, request, Jsonb(report)))
    return report_id


def list_for(user: User, limit: int = 30) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, request, created_at, reviewed_at FROM research_reports WHERE user_id = %s "
                            "ORDER BY created_at DESC LIMIT %s", (user.id, limit)).fetchall()
    return [{"id": str(r[0]), "request": r[1][:100], "created_at": r[2], "reviewed": r[3] is not None} for r in rows]


def get(user: User, report_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT report, created_at, reviewed_at FROM research_reports WHERE id = %s AND user_id = %s",
                           (report_id, user.id)).fetchone()
    if not row:
        return None
    return {**row[0], "id": report_id, "created_at": row[1], "reviewed_at": row[2]}


def mark_reviewed(user: User, report_id: str) -> bool:
    with _connect() as conn:
        return conn.execute("UPDATE research_reports SET reviewed_at = now() WHERE id = %s AND user_id = %s",
                            (report_id, user.id)).rowcount == 1


def delete(user: User, report_id: str) -> bool:
    with _connect() as conn:
        return conn.execute("DELETE FROM research_reports WHERE id = %s AND user_id = %s", (report_id, user.id)).rowcount == 1
