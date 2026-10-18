from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.services.vector_store import VectorStoreService
from app.services.reranker import rerank_passages

router = APIRouter(prefix="/retrieval", tags=["RAG Retrieval"])
vector_store = VectorStoreService()

class RetrievalRequest(BaseModel):
    query: str = Field(..., description="User search query")
    tenant_id: str = Field(..., description="Tenant identifier")
    user_id: str = Field(..., description="User UUID")
    user_level: int = Field(default=1, ge=1, le=4, description="User security clearance level")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of final parent passages to return")

@router.post("/search")
async def execute_retrieval(payload: RetrievalRequest):
    try:
        # Step 1: Broad hybrid RRF retrieval (fetch top 15 candidates)
        candidates = vector_store.secure_hybrid_rrf_search(
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            user_level=payload.user_level,
            query=payload.query,
            top_k=15
        )
        
        if not candidates:
            return {
                "status": "success",
                "query": payload.query,
                "matches_found": 0,
                "retrieved_passages": []
            }

        # Step 2: Precise cross-encoder reranking via Flashrank
        reranked_hits = rerank_passages(payload.query, candidates, top_k=payload.top_k)

        return {
            "status": "success",
            "query": payload.query,
            "matches_found": len(reranked_hits),
            "retrieved_passages": reranked_hits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
