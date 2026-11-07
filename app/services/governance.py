"""Personal-data rights and retention: see your data, erase it, and remove old records automatically."""
from typing import Any, Dict

import psycopg

from app.config import DATABASE_URL
from app.services.users import User

ERASED = "[erased]"


def export_user(user: User) -> Dict[str, Any]:
    """Everything the portal holds about this person, in one document."""
    with psycopg.connect(DATABASE_URL) as conn:
        convs = conn.execute("SELECT id, title, created_at FROM conversations WHERE user_id = %s ORDER BY created_at", (user.id,)).fetchall()
        msgs = conn.execute(
            "SELECT m.conversation_id, m.role, m.content, m.outcome, m.rating, m.feedback_comment, m.created_at "
            "FROM chat_messages m JOIN conversations c ON c.id = m.conversation_id WHERE c.user_id = %s ORDER BY m.id", (user.id,)).fetchall()
        audit = conn.execute(
            "SELECT created_at, query, outcome FROM audit_log WHERE user_id = %s ORDER BY created_at", (user.id,)).fetchall()
        reports = conn.execute("SELECT id, created_at, reviewed_at, report FROM research_reports WHERE user_id = %s ORDER BY created_at",
                               (user.id,)).fetchall()
    by_conv: Dict[str, list] = {}
    for cid, role, content, outcome, rating, comment, created in msgs:
        by_conv.setdefault(str(cid), []).append({"role": role, "content": content, "outcome": outcome,
                                                 "rating": rating, "feedback_comment": comment, "at": created})
    return {
        "account": {"email": user.email, "tenant": user.tenant_id, "level": user.level, "administrator": user.is_admin},
        "conversations": [{"id": str(c[0]), "title": c[1], "started": c[2], "messages": by_conv.get(str(c[0]), [])} for c in convs],
        "research_reports": [{"id": str(r[0]), "created": r[1], "reviewed": r[2], "report": r[3]} for r in reports],
        "questions_in_audit_log": [{"at": a[0], "question": a[1], "outcome": a[2]} for a in audit],
    }


def erase_user_data(user: User) -> Dict[str, int]:
    """Delete the person's conversations and scrub their words from the audit log.
    The audit rows stay (time, outcome, timing) so usage counts and accountability survive; the text does not."""
    with psycopg.connect(DATABASE_URL) as conn:
        convs = conn.execute("DELETE FROM conversations WHERE user_id = %s", (user.id,)).rowcount
        conn.execute("DELETE FROM research_reports WHERE user_id = %s", (user.id,))
        scrubbed = conn.execute(
            "UPDATE audit_log SET query = %s, answer = NULL, rewritten_query = NULL, trace = '[]'::jsonb, "
            "sources = '[]'::jsonb, user_email = %s WHERE user_id = %s AND query <> %s",
            (ERASED, ERASED, user.id, ERASED)).rowcount
    return {"conversations_deleted": convs, "audit_rows_scrubbed": scrubbed}


def purge_old(retention_days: int) -> Dict[str, int]:
    """Remove audit rows and conversations older than the retention period."""
    with psycopg.connect(DATABASE_URL) as conn:
        audit = conn.execute("DELETE FROM audit_log WHERE created_at < now() - make_interval(days => %s)", (retention_days,)).rowcount
        convs = conn.execute("DELETE FROM conversations WHERE updated_at < now() - make_interval(days => %s)", (retention_days,)).rowcount
    return {"audit_rows_deleted": audit, "conversations_deleted": convs}
