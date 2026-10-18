import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.services.chunker import HierarchicalChunker
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/documents", tags=["Documents"])
chunker = HierarchicalChunker(parent_size=200, child_size=50)
vector_store = VectorStoreService()

class IngestRequest(BaseModel):
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Raw text content")
    tenant_id: str = Field(..., description="Tenant identifier")
    classification_level: int = Field(default=1, ge=1, le=4)
    engagement_id: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)

@router.post("/ingest")
async def ingest_document(payload: IngestRequest):
    try:
        chunks = chunker.chunk_document(payload.content)
        if not chunks:
            raise HTTPException(status_code=400, detail="Document content is empty or invalid.")
        
        doc_id = str(uuid.uuid4())
        for item in chunks:
            vector_store.add_parent_and_children(
                parent_id=str(uuid.uuid4()),
                tenant_id=payload.tenant_id,
                document_id=doc_id,
                parent_content=item["parent_content"],
                child_chunks=item["child_chunks"],
                classification_level=payload.classification_level,
                engagement_id=payload.engagement_id,
                metadata={"title": payload.title, **(payload.metadata or {})}
            )
        return {
            "status": "success",
            "document_id": doc_id,
            "parents_created": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
