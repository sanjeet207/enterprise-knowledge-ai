"""Audit log export for compliance review. The file carries who asked what and how it ended. It never carries the
answer text or the cited passages, so exporting the log cannot copy restricted content out of the system."""
import csv
import io
from typing import Any, Dict, Iterable, List

import psycopg

from app.config import DATABASE_URL

COLUMNS = ("created_at", "user_email", "role_level", "query", "outcome", "top_score", "latency_ms", "model")
MAX_ROWS = 50000
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> str:
    """Text that a spreadsheet will not run as a formula. A question that starts with = or @ is typed by a user,
    so it is untrusted."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_STARTS) else text


def to_csv(rows: Iterable[Dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in rows:
        writer.writerow([safe_cell(row.get(c)) for c in COLUMNS])
    return out.getvalue()


def fetch(tenant_id: str, days: int) -> List[Dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM audit_log WHERE tenant_id = %s "
            "AND created_at >= now() - make_interval(days => %s) ORDER BY created_at DESC LIMIT %s",
            (tenant_id, days, MAX_ROWS)).fetchall()
    return [dict(zip(COLUMNS, r)) for r in rows]
