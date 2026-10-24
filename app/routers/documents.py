import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import IngestRequest
from app.security import require_level
from app.services import users
from app.services.chunker import HierarchicalChunker
from app.services.users import User
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/documents", tags=["Documents"])
chunker = HierarchicalChunker()
vector_store = VectorStoreService()

MIN_INGEST_LEVEL = 2  # managers and above may add documents


@router.post("/ingest")
def ingest_document(
    payload: IngestRequest,
    user: User = Depends(require_level(MIN_INGEST_LEVEL)),
):
    if payload.classification_level > user.level:
        raise HTTPException(status_code=403, detail="You cannot classify a document above your own level")

    engagement_id = str(payload.engagement_id) if payload.engagement_id else None
    if engagement_id and not users.is_engagement_member(engagement_id, user.id, user.tenant_id):
        raise HTTPException(status_code=403, detail="You can only add documents to engagements you belong to")

    chunks = chunker.chunk_document(payload.content)
    if not chunks:
        raise HTTPException(status_code=400, detail="Document content is empty or invalid.")

    document_id = str(uuid.uuid4())
    for item in chunks:
        vector_store.add_parent_and_children(
            parent_id=str(uuid.uuid4()),
            tenant_id=user.tenant_id,
            document_id=document_id,
            parent_content=item["parent_content"],
            child_chunks=item["child_chunks"],
            classification_level=payload.classification_level,
            engagement_id=engagement_id,
            metadata={**(payload.metadata or {}), "title": payload.title},
        )
    return {"status": "success", "document_id": document_id, "parents_created": len(chunks)}
