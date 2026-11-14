from functools import lru_cache
from typing import List, Dict, Any
from flashrank import Ranker, RerankRequest

from app import config
from app.services import model_cache

# Cross-encoder for precision. Stored in a permanent folder (see app/services/model_cache.py).
MODEL_NAME = "ms-marco-MiniLM-L-12-v2"


@lru_cache(maxsize=1)
def _get_ranker():
    return Ranker(model_name=MODEL_NAME, cache_dir=model_cache.prepare(model_cache.cache_dir(), MODEL_NAME))


def warm_up() -> None:
    """Load (and if needed download) the model now, so a problem shows up at setup, not on the first question."""
    _get_ranker()

def blend_order(by_rerank: List[int], mode: str, top_k: int) -> List[int]:
    """Which search positions to keep, best first.

    `by_rerank` lists search positions (0 = first search hit) in the reranker's order. Pure, unit-tested.
    none: the reranker's order. rrf: rank-fuse the reranker's order with the search order.
    guard: the reranker's order, but search position 0 is kept (it replaces the last place if it was dropped).
    """
    if mode == "rrf":
        score = {pos: 1.0 / (60 + pos + 1) + 1.0 / (60 + r + 1) for r, pos in enumerate(by_rerank)}
        return sorted(by_rerank, key=lambda p: score[p], reverse=True)[:top_k]
    kept = by_rerank[:top_k]
    if mode == "guard" and by_rerank and 0 not in kept:
        kept = kept[:-1] + [0] if kept else [0]
    return kept


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
    
    by_id = {}
    for res in results:
        res["meta"]["rerank_score"] = float(res["score"])
        by_id[res["id"]] = res["meta"]
    order = blend_order([res["id"] for res in results], config.RERANK_BLEND, top_k)
    return [by_id[i] for i in order]
