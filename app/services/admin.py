"""Database operations behind the administrator screens. Every query is limited to the administrator's own company."""
import uuid
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.config import DATABASE_URL
from app.security import hash_password
from app.services.users import User


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def record(actor: User, action: str, target: str, detail: Optional[dict] = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO admin_events (tenant_id, actor_id, actor_email, action, target, detail) VALUES (%s,%s,%s,%s,%s,%s)",
            (actor.tenant_id, actor.id, actor.email, action, target, Jsonb(detail or {})),
        )


def recent_events(tenant_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT created_at, actor_email, action, target FROM admin_events WHERE tenant_id = %s "
            "ORDER BY created_at DESC LIMIT %s", (tenant_id, limit)).fetchall()
    return [dict(zip(("created_at", "actor_email", "action", "target"), r)) for r in rows]


# ---------- documents (metadata only: an administrator manages documents without reading them) ----------
def list_documents(tenant_id: str, uploaded_by_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT p.document_id, MAX(p.metadata->>'title'), MAX(p.classification_level), MAX(e.name), "
            "COUNT(*), MAX(p.metadata->>'uploaded_by'), MIN(p.created_at), MAX(p.metadata->>'filename'), MAX(p.status), MAX(p.metadata->>'review_by'), MAX(p.metadata->>'version'), MAX(p.metadata->>'supersedes') "
            "FROM parent_chunks p LEFT JOIN engagements e ON e.id = p.engagement_id "
            "WHERE p.tenant_id = %s AND (%s::text IS NULL OR p.metadata->>'uploaded_by_id' = %s) "
            "GROUP BY p.document_id ORDER BY MIN(p.created_at) DESC", (tenant_id, uploaded_by_id, uploaded_by_id)).fetchall()
    keys = ("document_id", "title", "level", "team", "sections", "uploaded_by", "created_at", "filename", "status", "review_by", "version", "supersedes")
    docs = [dict(zip(keys, (str(r[0]),) + tuple(r[1:]))) for r in rows]
    for d in docs:
        d["version"] = int(d["version"] or 1)
    return docs


def find_by_hash(tenant_id: str, content_hash: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT metadata->>'title' FROM parent_chunks WHERE tenant_id = %s AND metadata->>'content_hash' = %s LIMIT 1",
            (tenant_id, content_hash)).fetchone()
    return row[0] if row else None


def document_info(tenant_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT metadata->>'title', metadata->>'uploaded_by_id' FROM parent_chunks "
            "WHERE tenant_id = %s AND document_id = %s LIMIT 1", (tenant_id, document_id)).fetchone()
    return {"title": row[0], "uploaded_by_id": row[1]} if row else None


def approve_document(tenant_id: str, document_id: str) -> int:
    with _connect() as conn:
        cur = conn.execute("UPDATE parent_chunks SET status = 'published' WHERE tenant_id = %s AND document_id = %s AND status = 'pending'",
                           (tenant_id, document_id))
        approved = cur.rowcount
        if approved:  # a new version replaces the one it supersedes
            conn.execute("UPDATE parent_chunks SET status = 'archived' WHERE tenant_id = %s AND status = 'published' "
                         "AND document_id::text = (SELECT MAX(metadata->>'supersedes') FROM parent_chunks WHERE tenant_id = %s AND document_id = %s)",
                         (tenant_id, tenant_id, document_id))
        return approved


def delete_document(tenant_id: str, document_id: str) -> int:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM parent_chunks WHERE tenant_id = %s AND document_id = %s", (tenant_id, document_id))
        return cur.rowcount


# ---------- teams (engagements) ----------
def engagement_exists(tenant_id: str, engagement_id: str) -> bool:
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM engagements WHERE id = %s AND tenant_id = %s",
                            (engagement_id, tenant_id)).fetchone() is not None


def user_engagements(tenant_id: str, user_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT e.id, e.name FROM engagements e JOIN engagement_members m ON m.engagement_id = e.id "
            "WHERE e.tenant_id = %s AND m.user_id = %s ORDER BY e.name", (tenant_id, user_id)).fetchall()
    return [{"id": str(r[0]), "name": r[1]} for r in rows]


def list_engagements(tenant_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        teams = conn.execute("SELECT id, name FROM engagements WHERE tenant_id = %s ORDER BY name", (tenant_id,)).fetchall()
        members = conn.execute(
            "SELECT m.engagement_id, u.id, u.email FROM engagement_members m JOIN users u ON u.id = m.user_id "
            "JOIN engagements e ON e.id = m.engagement_id WHERE e.tenant_id = %s ORDER BY u.email", (tenant_id,)).fetchall()
    by_team: Dict[str, list] = {}
    for team_id, user_id, email in members:
        by_team.setdefault(str(team_id), []).append({"user_id": str(user_id), "email": email})
    return [{"id": str(t[0]), "name": t[1], "members": by_team.get(str(t[0]), [])} for t in teams]


def create_engagement(tenant_id: str, name: str) -> str:
    team_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute("INSERT INTO engagements (id, tenant_id, name) VALUES (%s,%s,%s)", (team_id, tenant_id, name))
    return team_id


def add_member(tenant_id: str, engagement_id: str, user_id: str) -> bool:
    """False when the team or the person is not in this company."""
    with _connect() as conn:
        ok = conn.execute(
            "SELECT 1 FROM engagements e, users u WHERE e.id = %s AND u.id = %s AND e.tenant_id = %s AND u.tenant_id = %s",
            (engagement_id, user_id, tenant_id, tenant_id)).fetchone()
        if not ok:
            return False
        conn.execute("INSERT INTO engagement_members (engagement_id, user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                     (engagement_id, user_id))
    return True


def remove_member(tenant_id: str, engagement_id: str, user_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM engagement_members m USING engagements e WHERE m.engagement_id = e.id AND e.tenant_id = %s "
            "AND m.engagement_id = %s AND m.user_id = %s", (tenant_id, engagement_id, user_id))
        return cur.rowcount > 0


# ---------- people ----------
def list_users(tenant_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, email, role_level, is_active, is_admin, created_at, (locked_until IS NOT NULL AND locked_until > now()) FROM users "
                            "WHERE tenant_id = %s ORDER BY email", (tenant_id,)).fetchall()
    keys = ("id", "email", "level", "is_active", "is_admin", "created_at", "locked")
    return [dict(zip(keys, (str(r[0]),) + tuple(r[1:]))) for r in rows]


def create_user(tenant_id: str, email: str, password: Optional[str], level: int, is_admin: bool) -> Optional[str]:
    """None when the email is already taken (emails are unique across all companies)."""
    user_id = str(uuid.uuid4())
    try:
        with _connect() as conn:
            conn.execute("INSERT INTO users (id, tenant_id, email, role_level, password_hash, is_admin) VALUES (%s,%s,%s,%s,%s,%s)",
                         (user_id, tenant_id, email, level, hash_password(password) if password else None, is_admin))
    except UniqueViolation:
        return None
    return user_id


def update_user(tenant_id: str, user_id: str, changes: Dict[str, Any]) -> bool:
    columns = {"level": "role_level", "is_active": "is_active", "is_admin": "is_admin"}
    sets, values = [], []
    for key, column in columns.items():
        if key in changes:
            sets.append(f"{column} = %s")
            values.append(changes[key])
    if "password" in changes:
        sets.append("password_hash = %s")
        values.append(hash_password(changes["password"]))
    if "password" in changes or changes.get("is_active"):
        sets.append("failed_logins = 0")
        sets.append("locked_until = NULL")
    if not sets:
        return False
    with _connect() as conn:
        cur = conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = %s AND tenant_id = %s",
                           (*values, user_id, tenant_id))
        return cur.rowcount > 0


# ---------- insights (counts and unanswered questions, never who asked) ----------
def insights(tenant_id: str, days: int = 30) -> Dict[str, Any]:
    with _connect() as conn:
        outcomes = conn.execute(
            "SELECT outcome, COUNT(*) FROM audit_log WHERE tenant_id = %s AND created_at > now() - make_interval(days => %s) "
            "GROUP BY outcome", (tenant_id, days)).fetchall()
        latency = conn.execute(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) FROM audit_log "
            "WHERE tenant_id = %s AND outcome = 'answered' AND created_at > now() - make_interval(days => %s)",
            (tenant_id, days)).fetchone()[0]
        daily = conn.execute(
            "SELECT created_at::date, COUNT(*) FROM audit_log WHERE tenant_id = %s "
            "AND created_at > now() - make_interval(days => %s) GROUP BY 1 ORDER BY 1", (tenant_id, days)).fetchall()
        gaps = conn.execute(
            "SELECT lower(query), COUNT(*) FROM audit_log WHERE tenant_id = %s AND outcome = 'no_answer' "
            "AND created_at > now() - make_interval(days => %s) GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10",
            (tenant_id, days)).fetchall()
        votes = dict(conn.execute(
            "SELECT m.rating, COUNT(*) FROM chat_messages m JOIN conversations c ON c.id = m.conversation_id "
            "WHERE c.tenant_id = %s AND m.rating IS NOT NULL AND m.rated_at > now() - make_interval(days => %s) "
            "GROUP BY m.rating", (tenant_id, days)).fetchall())
        unhelpful = conn.execute(
            "SELECT lower(m.question), COUNT(*) FROM chat_messages m JOIN conversations c ON c.id = m.conversation_id "
            "WHERE c.tenant_id = %s AND m.rating = -1 AND m.rated_at > now() - make_interval(days => %s) "
            "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10", (tenant_id, days)).fetchall()
        overdue = conn.execute(
            "SELECT COUNT(DISTINCT document_id) FROM parent_chunks WHERE tenant_id = %s "
            "AND metadata->>'review_by' IS NOT NULL AND metadata->>'review_by' < to_char(current_date, 'YYYY-MM-DD')",
            (tenant_id,)).fetchone()[0]
    counts = {o: n for o, n in outcomes}
    total = sum(counts.values())
    return {
        "days": days, "total": total, "outcomes": counts,
        "answered_rate": round(counts.get("answered", 0) / total, 3) if total else None,
        "median_latency_ms": round(latency) if latency is not None else None,
        "daily": [{"day": str(d), "questions": n} for d, n in daily],
        "content_gaps": [{"question": q, "times": n} for q, n in gaps],
        "reviews_overdue": overdue,
        "feedback": {"helpful": votes.get(1, 0), "not_helpful": votes.get(-1, 0)},
        "unhelpful_questions": [{"question": q, "times": n} for q, n in unhelpful],
    }
