import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.security import get_current_user
from app.services import audit
from app.services.answer_check import (cited_numbers, clean_rewrites, is_insufficient, parse_verdict,
                                        strip_invalid_citations)
from app.services.llm import LLMService, LLMUnavailable
from app.services.reranker import rerank_passages
from app.services.users import User
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/chat", tags=["RAG Chat"])
vector_store = VectorStoreService()

CANDIDATES = 10

# One message for "nothing found" and "not relevant": a refusal must not reveal whether
# a restricted document exists.
REFUSAL = ("I can only answer from company documents you are authorized to access, "
           "and I couldn't find a reliable answer to this question.")
NO_ANSWER = "The documents available to you don't contain enough information to answer this."
UNVERIFIED = "I couldn't produce an answer that is backed by your documents, so I'm not showing one."


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=1000, description="User question")
    top_k: int = Field(default=3, ge=1, le=5, description="Passages given to the model")


@router.post("/query")
async def rag_query(payload: ChatRequest, user: User = Depends(get_current_user)):
    started = time.perf_counter()
    rewritten = None

    def finish(outcome, answer, sources=None, top_score=None, model=None):
        sources = sources or []
        audit.log_event(user, payload.query, outcome, top_score, sources, answer, model,
                        int((time.perf_counter() - started) * 1000), rewritten)
        return {"query": payload.query, "outcome": outcome, "answer": answer, "sources": sources}

    def retrieve(search_text: str):
        """Search and rerank. Access filtering by tenant, level and engagement happens in the SQL."""
        hits = vector_store.secure_hybrid_rrf_search(
            tenant_id=user.tenant_id, user_id=user.id, user_level=user.level,
            query=search_text, top_k=CANDIDATES,
        )
        return rerank_passages(search_text, hits, top_k=payload.top_k) if hits else []

    # 1. Retrieve and rerank.
    reranked = retrieve(payload.query)
    top_score = reranked[0]["rerank_score"] if reranked else 0.0

    # 2. Weak result: let the model rewrite the question as up to 3 keyword queries in formal policy
    #    wording (it sees the question only, never documents), search again, and keep the best result.
    #    The same access filter applies to every search.
    if top_score < config.REFUSAL_THRESHOLD:
        try:
            variants = clean_rewrites(await LLMService.rewrite_query(payload.query))
        except LLMUnavailable:
            variants = []
        variants = [v for v in variants if v.lower() != payload.query.lower()]
        if variants:
            rewritten = " | ".join(variants)  # recorded in the audit log even if it does not help
            for variant in variants:
                alt = retrieve(variant)
                alt_score = alt[0]["rerank_score"] if alt else 0.0
                if alt_score > top_score:
                    reranked, top_score = alt, alt_score

    # 3. Still not relevant: refuse without answering.
    if not reranked or top_score < config.REFUSAL_THRESHOLD:
        return finish("refused", REFUSAL, top_score=top_score)

    passages = [p["parent_content"] for p in reranked]

    # 4. Generate with numbered sources. Retry once if the answer has no valid citation.
    #    Then a second model call checks that every claim is supported; if not, regenerate (bounded).
    try:
        answer = await LLMService.generate_answer(payload.query, passages)
        if not is_insufficient(answer) and not cited_numbers(answer, len(passages)):
            answer = await LLMService.generate_answer(payload.query, passages, strict=True)

        if config.VALIDATOR_ENABLED:
            for attempt in range(config.VALIDATOR_MAX_RETRIES + 1):
                if is_insufficient(answer) or not cited_numbers(answer, len(passages)):
                    break  # handled below as no_answer / unverified
                verdict = await LLMService.verify_answer(payload.query, answer, passages)
                if parse_verdict(verdict):
                    break
                if attempt == config.VALIDATOR_MAX_RETRIES:
                    return finish("unverified", UNVERIFIED, top_score=top_score, model=config.LLM_MODEL)
                answer = await LLMService.generate_answer(payload.query, passages, strict=True, grounding=True)
    except LLMUnavailable:
        finish("error", None, top_score=top_score, model=config.LLM_MODEL)
        raise HTTPException(status_code=503, detail="The answer service is unavailable. Try again shortly.")

    if is_insufficient(answer):
        return finish("no_answer", NO_ANSWER, top_score=top_score, model=config.LLM_MODEL)

    cited = cited_numbers(answer, len(passages))
    if not cited:
        return finish("unverified", UNVERIFIED, top_score=top_score, model=config.LLM_MODEL)

    answer = strip_invalid_citations(answer, len(passages))
    sources = [
        {"number": n, "title": reranked[n - 1]["metadata"].get("title"),
         "score": round(reranked[n - 1]["rerank_score"], 4)}
        for n in cited
    ]
    return finish("answered", answer, sources, top_score, config.LLM_MODEL)
