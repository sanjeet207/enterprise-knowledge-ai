from fastapi import APIRouter, Depends

from app.schemas import SearchRequest
from app.security import get_current_user
from app.services.reranker import rerank_passages
from app.services.users import User
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])
vector_store = VectorStoreService()

CANDIDATES = 20


@router.post("/search")
def search(payload: SearchRequest, user: User = Depends(get_current_user)):
    candidates = vector_store.secure_hybrid_rrf_search(
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_level=user.level,
        query=payload.query,
        top_k=CANDIDATES,
    )
    if not candidates:
        return {"status": "success", "query": payload.query, "matches_found": 0, "retrieved_passages": []}

    reranked = rerank_passages(payload.query, candidates, top_k=payload.top_k)
    return {
        "status": "success",
        "query": payload.query,
        "matches_found": len(reranked),
        "retrieved_passages": reranked,
    }
