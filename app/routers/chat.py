from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.security import get_current_user
from app.services.vector_store import VectorStoreService
from app.services.reranker import rerank_passages
from app.services.llm import LLMService

router = APIRouter(prefix="/chat", tags=["RAG Chat"])
vector_store = VectorStoreService()

class ChatRequest(BaseModel):
    query: str = Field(..., description="User question")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of passages to feed to LLM")

@router.post("/query")
async def rag_query(payload: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        user_level = current_user["role_level"]

        # 1. Retrieve candidates via Hybrid RRF with strict tenant & RBAC isolation
        candidates = vector_store.secure_hybrid_rrf_search(
            tenant_id=tenant_id,
            user_id=user_id,
            user_level=user_level,
            query=payload.query,
            top_k=max(payload.top_k * 2, 5)
        )

        if not candidates:
            return {
                "query": payload.query,
                "answer": "I couldn't find any authorized documents matching your query.",
                "sources": []
            }

        # 2. Rerank passages using Flashrank cross-encoder
        reranked = rerank_passages(payload.query, candidates, top_k=payload.top_k)
        passages_text = [p["parent_content"] for p in reranked]

        # 3. Generate grounded answer via local Qwen 2.5
        answer = await LLMService.generate_answer(payload.query, passages_text)

        return {
            "query": payload.query,
            "answer": answer,
            "sources": [{"title": p["metadata"].get("title"), "score": p.get("rerank_score")} for p in reranked]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
