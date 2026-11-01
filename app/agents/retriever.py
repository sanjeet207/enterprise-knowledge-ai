"""Retriever: not an LLM. The only component that reads documents, and it enforces access.

Tenant, clearance level and engagement-team membership are applied inside the SQL query, so no model
ever receives a passage the user is not allowed to see.
"""
from app.services.reranker import rerank_passages

NAME = "retriever"
CANDIDATES = 10


class Retriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def run(self, user, search_text: str, top_k: int) -> list[dict]:
        hits = self.vector_store.secure_hybrid_rrf_search(
            tenant_id=user.tenant_id, user_id=user.id, user_level=user.level,
            query=search_text, top_k=CANDIDATES,
        )
        return rerank_passages(search_text, hits, top_k=top_k) if hits else []
