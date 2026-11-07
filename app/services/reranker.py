from functools import lru_cache
from typing import List, Dict, Any
from flashrank import Ranker, RerankRequest

from app.services import model_cache

# Cross-encoder for precision. Stored in a permanent folder (see app/services/model_cache.py).
MODEL_NAME = "ms-marco-MiniLM-L-12-v2"


@lru_cache(maxsize=1)
def _get_ranker():
    return Ranker(model_name=MODEL_NAME, cache_dir=model_cache.prepare(model_cache.cache_dir(), MODEL_NAME))


def warm_up() -> None:
    """Load (and if needed download) the model now, so a problem shows up at setup, not on the first question."""
    _get_ranker()

def rerank_passages(query: str, hits: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
    if not hits:
        return []
    
    ranker = _get_ranker()
    
    passages = [
        {
            "id": i,
            "text": h["parent_content"],
            "meta": h
        }
        for i, h in enumerate(hits)
    ]
    
    request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(request)
    
    reranked_hits = []
    for res in results[:top_k]:
        original_hit = res["meta"]
        original_hit["rerank_score"] = float(res["score"])
        reranked_hits.append(original_hit)
        
    return reranked_hits
