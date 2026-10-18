from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/retrieval", tags=["RAG Retrieval"])
vector_store = VectorStoreService()

class RetrievalRequest(BaseModel):
    query: str = Field(..., description="User search query")
    tenant_id: str = Field(..., description="Tenant identifier")
    user_id: str = Field(..., description="User UUID")
    user_level: int = Field(default=1, ge=1, le=4, description="User security clearance level")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of parent passages to retrieve")

@router.post("/search")
async def execute_retrieval(payload: RetrievalRequest):
    try:
        hits = vector_store.secure_hybrid_rrf_search(
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            user_level=payload.user_level,
            query=payload.query,
            top_k=payload.top_k
        )
        return {
            "status": "success",
            "query": payload.query,
            "matches_found": len(hits),
            "retrieved_passages": hits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
