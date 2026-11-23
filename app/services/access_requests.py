"""Requests for access.

A refusal never says whether a restricted document exists, so a request cannot name one. The person describes what
they need and why; an administrator decides. Approving records the decision. Changing the person's level or team is
a separate, audited step in Administration, so a request alone never widens what anyone can read."""
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import psycopg

from app.config import DATABASE_URL
from app.services.users import User

MAX_QUESTION = 1000
MAX_REASON = 500
MAX_NOTE = 500
MIN_REASON = 10
MAX_PENDING_PER_PERSON = 3
DECISIONS = ("approved", "denied")


def _tidy(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_request(question: Optional[str], reason: Optional[str]) -> Tuple[str, str]:
    """The question the person asked and their business reason, trimmed. Raises ValueError with a plain message."""
    q, r = _tidy(question), _tidy(reason)
    if not q:
        raise ValueError("Say what you need access to.")
    if len(q) > MAX_QUESTION:
        raise ValueError(f"Keep the request under {MAX_QUESTION} characters.")
    if len(r) < MIN_REASON:
        raise ValueError("Give a short business reason (at least a few words) so an administrator can decide.")
    if len(r) > MAX_REASON:
        raise ValueError(f"Keep the reason under {MAX_REASON} characters.")
    return q, r


def check_decision(status: str, decision: str, note: Optional[str], decider_id: str, requester_id: str) -> str:
    """The cleaned decision note. Raises ValueError (bad input) or PermissionError (not allowed)."""
    if decision not in DECISIONS:
        raise ValueError("Decide 'approved' or 'denied'.")
    if status != "pending":
        raise ValueError("This request has already been decided.")
    if decider_id == requester_id:
        raise PermissionError("You cannot decide your own request. Ask another administrator.")
    cleaned = _tidy(note)
    if len(cleaned) > MAX_NOTE:
        raise ValueError(f"Keep the note under {MAX_NOTE} characters.")
    if decision == "denied" and len(cleaned) < 3:
        raise ValueError("Say why the request is denied, so the person knows what to do next.")
    return cleaned


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


_KEYS = ("id", "user_email", "question", "reason", "status", "decided_by", "decided_at", "decision_note", "created_at")
_COLUMNS = "id, user_email, question, reason, status, decided_by, decided_at, decision_note, created_at"


def _rows(rows) -> List[Dict[str, Any]]:
    return [dict(zip(_KEYS, (str(r[0]),) + tuple(r[1:]))) for r in rows]


def create(user: User, question: str, reason: str) -> str:
    """Raises ValueError when the person already has the maximum number of open requests."""
    with _connect() as conn:
        open_now = conn.execute("SELECT count(*) FROM access_requests WHERE user_id = %s AND status = 'pending'",
                                (user.id,)).fetchone()[0]
        if open_now >= MAX_PENDING_PER_PERSON:
            raise ValueError("You already have the maximum number of open requests. Wait for a decision first.")
        request_id = str(uuid.uuid4())
        conn.execute("INSERT INTO access_requests (id, tenant_id, user_id, user_email, question, reason) "
                     "VALUES (%s,%s,%s,%s,%s,%s)", (request_id, user.tenant_id, user.id, user.email, question, reason))
    return request_id


def list_mine(user: User) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(f"SELECT {_COLUMNS} FROM access_requests WHERE user_id = %s "
                            "ORDER BY created_at DESC LIMIT 50", (user.id,)).fetchall()
    return _rows(rows)


def list_for_admin(tenant_id: str, only_pending: bool) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(f"SELECT {_COLUMNS} FROM access_requests WHERE tenant_id = %s "
                            "AND (NOT %s OR status = 'pending') ORDER BY created_at DESC LIMIT 200",
                            (tenant_id, only_pending)).fetchall()
    return _rows(rows)


def get(tenant_id: str, request_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(f"SELECT {_COLUMNS}, user_id FROM access_requests WHERE id = %s AND tenant_id = %s",
                           (request_id, tenant_id)).fetchone()
    if not row:
        return None
    found = dict(zip(_KEYS, (str(row[0]),) + tuple(row[1:9])))
    found["user_id"] = str(row[9])
    return found


def decide(tenant_id: str, request_id: str, decider_email: str, decision: str, note: str) -> bool:
    """Records the decision only if the request is still pending (two administrators cannot both decide it)."""
    with _connect() as conn:
        done = conn.execute("UPDATE access_requests SET status = %s, decided_by = %s, decided_at = now(), "
                            "decision_note = %s WHERE id = %s AND tenant_id = %s AND status = 'pending'",
                            (decision, decider_email, note or None, request_id, tenant_id)).rowcount
    return done == 1
