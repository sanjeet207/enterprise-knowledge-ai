import hashlib
import uuid
from typing import Optional

import psycopg

from app.config import DATABASE_URL
from app.services import admin
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


def ingest_document(user: User, title: str, content: str, level: int,
                    engagement_id: Optional[str], filename: Optional[str] = None) -> dict:
    """Add one document to the caller's own company. The caller has already checked upload_policy."""
    if engagement_id and not admin.engagement_exists(user.tenant_id, engagement_id):
        raise IngestError(404, "That team does not exist in your company")
    content_hash = hashlib.sha256(" ".join(content.split()).encode("utf-8")).hexdigest()
    existing = admin.find_by_hash(user.tenant_id, content_hash)
    if existing:
        raise IngestError(409, f'This content is already in the knowledge base as "{existing}"')
    chunks = chunker.chunk_document(content)
    if not chunks:
        raise IngestError(400, "Document content is empty or invalid.")
    document_id = str(uuid.uuid4())
    # Maker-checker: an administrator publishes directly; anyone else's upload waits for an administrator to approve it.
    status = "published" if user.is_admin else "pending"
    metadata = {"title": title, "uploaded_by": user.email, "uploaded_by_id": user.id,
                "content_hash": content_hash, "filename": filename}
    try:
        for item in chunks:
            vector_store.add_parent_and_children(
                parent_id=str(uuid.uuid4()), tenant_id=user.tenant_id, document_id=document_id,
                parent_content=item["parent_content"], child_chunks=item["child_chunks"],
                classification_level=level, engagement_id=engagement_id, metadata=metadata, status=status,
            )
    except Exception:
        # Never leave half a document behind: remove what was written and report the failure.
        admin.delete_document(user.tenant_id, document_id)
        raise
    admin.record(user, "document.upload", title, {"document_id": document_id, "level": level,
                                                  "engagement_id": engagement_id, "filename": filename, "status": status})
    return {"document_id": document_id, "title": title, "parents_created": len(chunks), "status": status}
