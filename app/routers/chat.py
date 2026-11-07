from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agents import orchestrator
from app import config
from app.agents.retriever import Retriever
from app.security import get_current_user
from app.services.llm import LLMUnavailable
from app.services.ratelimit import SlidingWindow
from app.services.users import User
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/chat", tags=["RAG Chat"])
retriever = Retriever(VectorStoreService())
limiter = SlidingWindow(config.CHAT_RATE_PER_MINUTE)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=1000, description="User question")
    top_k: int = Field(default=3, ge=1, le=5, description="Passages given to the model")


@router.post("/query")
async def rag_query(payload: ChatRequest, user: User = Depends(get_current_user)):
    if not limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a moment.", headers={"Retry-After": "60"})
    try:
        return await orchestrator.answer_question(user, payload.query, payload.top_k, retriever)
    except LLMUnavailable:
        raise HTTPException(status_code=503, detail="The answer service is unavailable. Try again shortly.")
