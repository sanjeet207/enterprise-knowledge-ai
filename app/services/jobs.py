"""A small job queue in PostgreSQL: uploads are accepted quickly and indexed by a background worker.

Why PostgreSQL and not Redis/Celery: the database is already there, a job is written in the same transaction
model as the data, and `FOR UPDATE SKIP LOCKED` lets several workers take different jobs without a lock fight.
If volume grows, the same interface can sit on a broker without changing the callers.
"""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.types.json import Jsonb

from app import config
from app.services import ingest, job_policy, metrics, upload_policy, users
from app.services.users import User

log = logging.getLogger("jobs")

COLUMNS = ("id, user_id, document_id, title, status, attempts, error, error_status, result, payload, "
           "created_at, finished_at")


def _connect() -> psycopg.Connection:
    return psycopg.connect(config.DATABASE_URL)


def _view(row) -> Dict[str, Any]:
    result, payload = row[8] or {}, row[9] or {}
    return {"job_id": str(row[0]), "uploaded_by_id": str(row[1]), "document_id": str(row[2]), "title": row[3],
            "status": row[4], "attempts": row[5], "error": row[6], "error_status": row[7],
            "version": result.get("version", payload.get("version", 1)),
            "publish_status": result.get("status", payload.get("status")),
            "parents_created": result.get("parents_created"),
            "created_at": row[10].isoformat() if row[10] else None,
            "finished_at": row[11].isoformat() if row[11] else None}


def enqueue(user: User, *, document_id: str, title: str, content: str, level: int, engagement_id: Optional[str],
            filename: Optional[str], review_by: Optional[str], previous: Optional[dict], status: str,
            content_hash: str, version: int) -> str:
    job_id = str(uuid.uuid4())
    payload = {"level": level, "engagement_id": engagement_id, "filename": filename, "review_by": review_by,
               "previous": previous, "status": status, "content_hash": content_hash, "version": version}
    with _connect() as conn:
        waiting = conn.execute(
            "SELECT COUNT(*) FROM ingest_jobs WHERE tenant_id = %s AND user_id = %s AND status IN ('queued', 'processing')",
            (user.tenant_id, user.id)).fetchone()[0]
        if waiting >= job_policy.MAX_PENDING_PER_USER:
            raise ingest.IngestError(429, "You already have many uploads waiting. Please wait for them to finish.")
        conn.execute(
            "INSERT INTO ingest_jobs (id, tenant_id, user_id, document_id, title, content, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (job_id, user.tenant_id, user.id, document_id, title, content, Jsonb(payload)))
    metrics.inc("ingest_jobs", result="queued")
    return job_id


def get(tenant_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(f"SELECT {COLUMNS} FROM ingest_jobs WHERE tenant_id = %s AND id = %s",
                           (tenant_id, job_id)).fetchone()
    return _view(row) if row else None


def list_recent(tenant_id: str, user_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    sql, args = f"SELECT {COLUMNS} FROM ingest_jobs WHERE tenant_id = %s", [tenant_id]
    if user_id:
        sql += " AND user_id = %s"
        args.append(user_id)
    sql += " ORDER BY created_at DESC LIMIT %s"
    args.append(limit)
    with _connect() as conn:
        return [_view(r) for r in conn.execute(sql, args).fetchall()]


def claim() -> Optional[Dict[str, Any]]:
    """Take the oldest due job. SKIP LOCKED: if another worker holds a row, move on to the next one."""
    with _connect() as conn:
        row = conn.execute(
            "UPDATE ingest_jobs SET status = 'processing', started_at = now(), attempts = attempts + 1 "
            "WHERE id = (SELECT id FROM ingest_jobs WHERE status = 'queued' AND run_after <= now() "
            "            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) "
            "RETURNING id, tenant_id, user_id, document_id, title, content, payload, attempts").fetchone()
    if not row:
        return None
    return {"id": str(row[0]), "tenant_id": row[1], "user_id": str(row[2]), "document_id": str(row[3]),
            "title": row[4], "content": row[5], "payload": row[6] or {}, "attempts": row[7]}


def requeue_stuck() -> int:
    """Jobs left 'processing' by a worker that died: try again, or fail them if they used up their attempts."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE ingest_jobs SET status = CASE WHEN attempts >= %s THEN 'failed' ELSE 'queued' END, "
            "error = 'The worker stopped while processing this upload', "
            "error_status = CASE WHEN attempts >= %s THEN 500 ELSE NULL END, "
            "finished_at = CASE WHEN attempts >= %s THEN now() ELSE NULL END, "
            "content = CASE WHEN attempts >= %s THEN '' ELSE content END "
            "WHERE status = 'processing' AND started_at < now() - make_interval(secs => %s::float8)",
            (job_policy.MAX_ATTEMPTS,) * 4 + (job_policy.STUCK_AFTER_SECONDS,))
        return cur.rowcount


def _done(job_id: str, result: dict) -> None:
    with _connect() as conn:
        conn.execute("UPDATE ingest_jobs SET status = 'done', finished_at = now(), content = '', error = NULL, "
                     "result = %s WHERE id = %s", (Jsonb(result), job_id))


def _failed(job: dict, message: str, status_code: int, permanent: bool) -> str:
    next_status, delay = job_policy.after_failure(job["attempts"], permanent)
    with _connect() as conn:
        if next_status == "queued":
            conn.execute("UPDATE ingest_jobs SET status = 'queued', error = %s, "
                         "run_after = now() + make_interval(secs => %s::float8) WHERE id = %s",
                         (message[:300], float(delay), job["id"]))
        else:
            conn.execute("UPDATE ingest_jobs SET status = 'failed', finished_at = now(), content = '', error = %s, "
                         "error_status = %s WHERE id = %s", (message[:300], status_code, job["id"]))
    return next_status


def run_one() -> bool:
    """Process one job if there is one. Returns False when the queue is empty."""
    job = claim()
    if job is None:
        return False
    started = time.perf_counter()
    try:
        # Nothing from the queue is trusted: who the person is and what they may do is read again, now.
        user = users.get_by_id(job["user_id"])
        if user is None or not user.is_active or user.tenant_id != job["tenant_id"]:
            raise ingest.IngestError(403, "The account that sent this upload is no longer active")
        p = job["payload"]
        engagement = p.get("engagement_id")
        is_member = bool(engagement) and users.is_engagement_member(engagement, user.id, user.tenant_id)
        try:
            upload_policy.check_upload(user.is_admin, user.level, p["level"], engagement, is_member)
        except PermissionError as exc:
            raise ingest.IngestError(403, str(exc))
        status = job_policy.publish_status(p.get("status", "pending"), user.is_admin)
        result = ingest.index_document(user, job["document_id"], job["title"], job["content"], p["level"], engagement,
                                       p.get("filename"), p.get("review_by"), p.get("previous"), status, p["content_hash"])
    except ingest.IngestError as exc:
        _failed(job, exc.message, exc.status, permanent=True)
        metrics.inc("ingest_jobs", result="failed")
        log.warning("ingest job %s failed: %s", job["id"], exc.message)
    except Exception as exc:  # noqa: BLE001 - a bad job must never stop the worker
        outcome = _failed(job, f"{exc.__class__.__name__}: {exc}", 500, permanent=False)
        metrics.inc("ingest_jobs", result="retry" if outcome == "queued" else "failed")
        log.exception("ingest job %s hit an error (attempt %s)", job["id"], job["attempts"])
    else:
        _done(job["id"], result)
        metrics.inc("ingest_jobs", result="done")
        log.info("ingest job %s done in %.1fs", job["id"], time.perf_counter() - started)
    return True
