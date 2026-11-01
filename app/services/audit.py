import logging
from typing import Any, List, Optional

import psycopg
from psycopg.types.json import Jsonb

from app.config import DATABASE_URL
from app.services.users import User

logger = logging.getLogger(__name__)


def log_event(
    user: User,
    query: str,
    outcome: str,
    top_score: Optional[float],
    sources: List[dict],
    answer: Optional[str],
    model: Optional[str],
    latency_ms: int,
    rewritten_query: Optional[str] = None,
) -> None:
    """Write one audit row. Best effort: a failure is logged but never breaks the request."""
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                "INSERT INTO audit_log (tenant_id, user_id, user_email, role_level, query, outcome, "
                "top_score, sources, answer, model, latency_ms, rewritten_query) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user.tenant_id, user.id, user.email, user.level, query, outcome,
                 top_score, Jsonb(sources), answer, model, latency_ms, rewritten_query),
            )
    except Exception:
        logger.exception("Audit write failed")


def recent_events(tenant_id: str, limit: int = 50) -> List[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT created_at, user_email, role_level, query, outcome, top_score, sources, model, latency_ms, rewritten_query "
            "FROM audit_log WHERE tenant_id = %s ORDER BY created_at DESC LIMIT %s",
            (tenant_id, limit),
        ).fetchall()
    keys = ["created_at", "user_email", "role_level", "query", "outcome", "top_score", "sources", "model", "latency_ms", "rewritten_query"]
    return [dict(zip(keys, r)) for r in rows]
