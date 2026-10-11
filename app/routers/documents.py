import uuid

from fastapi import APIRouter, HTTPException

from app.schemas import DocumentIngestRequest
from app.services.chunker import TextChunker
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/documents", tags=["Documents"])
chunker = TextChunker()
vector_store = VectorStoreService()


@router.post("/ingest")
async def ingest_document(payload: DocumentIngestRequest):
    # TODO (Week 7): take tenant_id from the verified JWT, never from the request body
    chunks = chunker.chunk_text(payload.content)
    if not chunks:
        raise HTTPException(status_code=400, detail="Document content is empty or invalid.")

    doc_id = str(uuid.uuid4())
    vector_store.add_documents(
        tenant_id=payload.tenant_id,
        document_id=doc_id,
        chunks=chunks,
        metadata={"title": payload.title, **(payload.metadata or {})},
    )
    return {
        "status": "success",
        "document_id": doc_id,
        "tenant_id": payload.tenant_id,
        "chunks_created": len(chunks),
    }
