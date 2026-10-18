from functools import lru_cache
from typing import List, Dict, Any
from flashrank import Ranker, RerankRequest

@lru_cache(maxsize=1)
def _get_ranker():
    # Using ms-marco-MiniLM-L-12-v2 for cross-encoder precision
    return Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank_cache")

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
