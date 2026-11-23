import asyncio
import hashlib
import uuid
from typing import Optional

from app import config
from app.services import admin, content_scan, versions
from app.services.chunker import HierarchicalChunker
from app.services.users import User
from app.services.vector_store import VectorStoreService

chunker = HierarchicalChunker()
vector_store = VectorStoreService()


class IngestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def inspect_text(content: str) -> Optional[str]:
    """Ask the reviewer model whether the text gives instructions to an AI. Runs in a worker or request thread."""
    from app.agents import inspector
    return asyncio.run(inspector.scan(content))


def status_for(user: User) -> str:
    """Maker-checker: an administrator publishes directly; anyone else's upload waits for an administrator to approve it."""
    return "published" if user.is_admin else "pending"


def duplicate_message(existing: dict) -> str:
    """Name the existing document only to someone who may read it; otherwise say nothing about which one it is."""
    if existing.get("readable"):
        return f'This content is already in the knowledge base as "{existing["title"]}"'
    return "This content is already in the knowledge base."


def precheck(user: User, content: str, engagement_id: Optional[str]) -> str:
    """The quick checks done while the person waits. Returns the content hash. Nothing is written."""
    if engagement_id and not admin.engagement_exists(user.tenant_id, engagement_id):
        raise IngestError(404, "That team does not exist in your company")
    reason = content_scan.suspicious(content)
    if reason:
        raise IngestError(422, f"This document was not added: {reason}. Ask a security reviewer to look at it.")
    content_hash = hashlib.sha256(" ".join(content.split()).encode("utf-8")).hexdigest()
    existing = admin.find_by_hash(user.tenant_id, content_hash, user.level, user.id)
    if existing:
        raise IngestError(409, duplicate_message(existing))
    if not chunker.chunk_document(content):
        raise IngestError(400, "Document content is empty or invalid.")
    return content_hash


def index_document(user: User, document_id: str, title: str, content: str, level: int,
                   engagement_id: Optional[str], filename: Optional[str], review_by: Optional[str],
                   previous: Optional[dict], status: str, content_hash: str) -> dict:
    """The slow part: chunk, embed and store. Safe to run again (retries) and re-checks what may have changed in the queue."""
    chunks = chunker.chunk_document(content)
    if not chunks:
        raise IngestError(400, "Document content is empty or invalid.")
    # Idempotent: a retry after a crash that happened after the write must not fail as a "duplicate" of itself.
    already = versions.info(user.tenant_id, document_id)
    if already and already["status"] == "indexing":
        admin.delete_document(user.tenant_id, document_id)  # an earlier attempt died half way: start clean
        already = None
    if already:
        return {"document_id": document_id, "title": title, "parents_created": len(chunks), "status": status,
                "version": (previous["version"] + 1) if previous else 1}
    existing = admin.find_by_hash(user.tenant_id, content_hash, user.level, user.id)
    if existing:
        raise IngestError(409, duplicate_message(existing))
    if previous:
        current = versions.info(user.tenant_id, previous["document_id"])
        if current is None or current["status"] != "published":
            raise IngestError(409, "The document this was meant to replace has changed or been removed in the meantime")
    # The reviewer model is less precise than the upload patterns, so what it flags is held for a second
    # administrator to read (with the quoted sentence), not thrown away: a false alarm costs a review, not a lost document.
    review_note = None
    if config.INSPECT_UPLOADS:
        reason = inspect_text(content)
        if reason:
            status = "pending"
            review_note = f"Held for review: {reason}"
    metadata = {"title": title, "uploaded_by": user.email, "uploaded_by_id": user.id,
                "content_hash": content_hash, "filename": filename, "review_by": review_by, "review_note": review_note}
    if previous:
        metadata.update({"doc_key": previous["doc_key"], "version": previous["version"] + 1, "supersedes": previous["document_id"]})
    try:
        for item in chunks:
            vector_store.add_parent_and_children(
                parent_id=str(uuid.uuid4()), tenant_id=user.tenant_id, document_id=document_id,
                parent_content=item["parent_content"], child_chunks=item["child_chunks"],
                classification_level=level, engagement_id=engagement_id, metadata=metadata, status="indexing",
            )
        versions.promote(user.tenant_id, document_id, status)  # all chunks become visible together
    except Exception:
        # Never leave half a document behind: remove what was written and report the failure.
        admin.delete_document(user.tenant_id, document_id)
        raise
    if previous and status == "published":
        versions.archive(user.tenant_id, previous["document_id"])
    admin.record(user, "document.upload", title, {"document_id": document_id, "level": level,
                                                  "engagement_id": engagement_id, "filename": filename, "status": status,
                                                  "supersedes": previous["document_id"] if previous else None})
    return {"document_id": document_id, "title": title, "parents_created": len(chunks), "status": status,
            "version": metadata.get("version", 1), "review_note": review_note}


def ingest_document(user: User, title: str, content: str, level: int,
                    engagement_id: Optional[str], filename: Optional[str] = None,
                    review_by: Optional[str] = None, previous: Optional[dict] = None) -> dict:
    """Check and index in one go, inside the request. The caller has already checked upload_policy."""
    content_hash = precheck(user, content, engagement_id)
    return index_document(user, str(uuid.uuid4()), title, content, level, engagement_id, filename, review_by,
                          previous, status_for(user), content_hash)
