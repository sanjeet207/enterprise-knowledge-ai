"""Saved conversations. Everything is scoped to the person who owns it: another person's id is simply 'not found'."""
import uuid
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import psycopg
from psycopg.types.json import Jsonb

from app.config import DATABASE_URL
from app.services.users import User


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def owns(user: User, conversation_id: str) -> bool:
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM conversations WHERE id = %s AND user_id = %s",
                            (conversation_id, user.id)).fetchone() is not None


def create(user: User, title: str) -> str:
    conversation_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute("INSERT INTO conversations (id, tenant_id, user_id, title) VALUES (%s,%s,%s,%s)",
                     (conversation_id, user.tenant_id, user.id, title[:80]))
    return conversation_id


def recent_questions(conversation_id: str, limit: int = 3) -> List[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT content FROM chat_messages WHERE conversation_id = %s AND role = 'user' "
                            "ORDER BY id DESC LIMIT %s", (conversation_id, limit)).fetchall()
    return [r[0] for r in reversed(rows)]


def without_excerpts(sources: list) -> list:
    """Sources as stored with a saved conversation: title, number and score, never the passage text."""
    return [{key: value for key, value in source.items() if key != "excerpt"} for source in sources or []]


def add_exchange(conversation_id: str, question: str, answer: str, outcome: str, sources: list) -> int:
    """Store the question and the answer together. Returns the answer's message id (for feedback)."""
    with _connect() as conn:
        conn.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (%s,'user',%s)",
                     (conversation_id, question))
        message_id = conn.execute(
            "INSERT INTO chat_messages (conversation_id, role, content, question, outcome, sources) "
            "VALUES (%s,'assistant',%s,%s,%s,%s) RETURNING id",
            (conversation_id, answer or "", question, outcome, Jsonb(sources or []))).fetchone()[0]
        conn.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,))
    return message_id


def list_for(user: User, limit: int = 50) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, title, updated_at FROM conversations WHERE user_id = %s "
                            "ORDER BY updated_at DESC LIMIT %s", (user.id, limit)).fetchall()
    return [{"id": str(r[0]), "title": r[1], "updated_at": r[2]} for r in rows]


REDACTED_NOTICE = ("This answer used a document you can no longer open, so it is hidden. "
                   "Ask the question again to get an answer based on what you can see now.")


def accessible_documents(user: User) -> Tuple[Set[str], Set[str]]:
    """Ids and lower-cased titles of the documents this person may read right now.

    Same rule as the search query (vector_store.SECURE_RRF_SQL): their company, published, at or below their level,
    and for engagement documents only while they are on the team. Level and team are read from the database here,
    never from the token, so a change takes effect at once."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT document_id::text, lower(coalesce(metadata->>'title', '')) FROM parent_chunks "
            "WHERE tenant_id = %s AND status = 'published' AND classification_level <= %s "
            "AND (engagement_id IS NULL OR engagement_id IN (SELECT engagement_id FROM engagement_members WHERE user_id = %s))",
            (user.tenant_id, user.level, user.id)).fetchall()
    return {r[0] for r in rows}, {r[1] for r in rows if r[1]}


def _still_open(source: dict, document_ids: Set[str], titles: Set[str]) -> bool:
    """Fail closed. Newer messages carry the document id. Older ones only have a title, matched against current titles."""
    if source.get("document_id"):
        return str(source["document_id"]) in document_ids
    return str(source.get("title") or "").strip().lower() in titles


def apply_current_access(messages: Iterable[Dict[str, Any]], document_ids: Set[str], titles: Set[str]) -> List[Dict[str, Any]]:
    """What an old conversation may show today.

    The person's own questions stay. An answer built on any document they can no longer open is replaced by a notice,
    because the answer text carries that document's content, and its source list is emptied. Answers that cite only
    documents still open, and refusals (no sources), are unchanged."""
    out = []
    for message in messages:
        sources = message.get("sources") or []
        if message.get("role") != "assistant" or not sources or all(_still_open(s, document_ids, titles) for s in sources):
            out.append(message)
            continue
        out.append(dict(message, content=REDACTED_NOTICE, outcome="redacted", sources=[], redacted=True))
    return out


def with_current_access(user: User, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not any(m.get("sources") for m in messages):
        return messages
    document_ids, titles = accessible_documents(user)
    return apply_current_access(messages, document_ids, titles)


def messages(user: User, conversation_id: str) -> Optional[List[Dict[str, Any]]]:
    if not owns(user, conversation_id):
        return None
    with _connect() as conn:
        rows = conn.execute("SELECT id, role, content, outcome, sources, rating FROM chat_messages "
                            "WHERE conversation_id = %s ORDER BY id", (conversation_id,)).fetchall()
    keys = ("id", "role", "content", "outcome", "sources", "rating")
    return with_current_access(user, [dict(zip(keys, r)) for r in rows])


def delete(user: User, conversation_id: str) -> bool:
    with _connect() as conn:
        return conn.execute("DELETE FROM conversations WHERE id = %s AND user_id = %s",
                            (conversation_id, user.id)).rowcount > 0


def rate(user: User, message_id: int, rating: int, comment: Optional[str]) -> bool:
    """Only the owner of the conversation can rate its answers, and only answers (not questions)."""
    with _connect() as conn:
        return conn.execute(
            "UPDATE chat_messages m SET rating = %s, feedback_comment = %s, rated_at = now() "
            "FROM conversations c WHERE m.id = %s AND m.role = 'assistant' AND m.conversation_id = c.id AND c.user_id = %s",
            (rating, (comment or "").strip()[:500] or None, message_id, user.id)).rowcount > 0
