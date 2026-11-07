"""Document versions: finding a document's history and reading text under the caller's own access rules."""
from typing import Any, Dict, List, Optional

import psycopg

from app.config import DATABASE_URL
from app.services.users import User

READABLE = "('published', 'archived')"


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def info(tenant_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(metadata->>'title'), MAX(classification_level), MAX(engagement_id::text), MAX(status), "
            "MAX(metadata->>'doc_key'), MAX(metadata->>'version'), MAX(metadata->>'uploaded_by_id') "
            "FROM parent_chunks WHERE tenant_id = %s AND document_id = %s HAVING COUNT(*) > 0",
            (tenant_id, document_id)).fetchone()
    if not row:
        return None
    return {"title": row[0], "level": row[1], "engagement_id": row[2], "status": row[3],
            "doc_key": row[4] or document_id, "version": int(row[5] or 1), "uploaded_by_id": row[6]}


def archive(tenant_id: str, document_id: str) -> int:
    with _connect() as conn:
        return conn.execute("UPDATE parent_chunks SET status = 'archived' WHERE tenant_id = %s AND document_id = %s "
                            "AND status = 'published'", (tenant_id, document_id)).rowcount


def readable_text(user: User, document_id: str) -> Optional[Dict[str, Any]]:
    """The document's text if this person may read it (same level, team and company rules as search)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT content, metadata->>'title', metadata->>'version' FROM parent_chunks "
            "WHERE document_id = %s AND tenant_id = %s AND classification_level <= %s AND status IN " + READABLE + " "
            "AND (engagement_id IS NULL OR engagement_id IN (SELECT engagement_id FROM engagement_members WHERE user_id = %s)) "
            "ORDER BY created_at", (document_id, user.tenant_id, user.level, user.id)).fetchall()
    if not rows:
        return None
    return {"title": rows[0][1], "version": int(rows[0][2] or 1), "text": " ".join(r[0] for r in rows)}


def history(user: User, doc_key: str) -> List[Dict[str, Any]]:
    """Every version of one document that this person may read, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT document_id, MAX(metadata->>'version'), MAX(status), MIN(created_at), MAX(metadata->>'uploaded_by') "
            "FROM parent_chunks WHERE tenant_id = %s AND classification_level <= %s AND status IN " + READABLE + " "
            "AND (metadata->>'doc_key' = %s OR document_id::text = %s) "
            "AND (engagement_id IS NULL OR engagement_id IN (SELECT engagement_id FROM engagement_members WHERE user_id = %s)) "
            "GROUP BY document_id", (user.tenant_id, user.level, doc_key, doc_key, user.id)).fetchall()
    found = [{"document_id": str(r[0]), "version": int(r[1] or 1), "status": r[2], "created_at": r[3], "uploaded_by": r[4]} for r in rows]
    return sorted(found, key=lambda v: v["version"], reverse=True)
