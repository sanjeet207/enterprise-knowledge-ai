from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agents import condenser, orchestrator
from app import config
from app.agents.retriever import Retriever
from app.security import get_current_user
from app.services import conversations, followup, metrics
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
    conversation_id: Optional[UUID] = Field(default=None, description="Continue this saved conversation")


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(..., description="1 = helpful, -1 = not helpful")
    comment: Optional[str] = Field(default=None, max_length=500)


@router.post("/query")
async def rag_query(payload: ChatRequest, user: User = Depends(get_current_user)):
    if not limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a moment.", headers={"Retry-After": "60"})
    conversation_id = str(payload.conversation_id) if payload.conversation_id else None
    if conversation_id and not conversations.owns(user, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    previous = conversations.recent_questions(conversation_id) if conversation_id else []
    question = payload.query
    try:
        if followup.needs_context(question, previous):
            try:
                question = await condenser.run(previous, question)
            except LLMUnavailable:
                question = payload.query  # the normal pipeline below reports the outage
        result = await orchestrator.answer_question(user, question, payload.top_k, retriever)
    except LLMUnavailable:
        raise HTTPException(status_code=503, detail="The answer service is unavailable. Try again shortly.")
    metrics.inc("chat_outcomes_total", outcome=result["outcome"])
    if question != payload.query:
        result["corrected_query"] = question
    if not conversation_id:
        conversation_id = conversations.create(user, payload.query)
    result["conversation_id"] = conversation_id
    result["message_id"] = conversations.add_exchange(
        conversation_id, payload.query, result.get("answer") or "", result["outcome"], result.get("sources") or [])
    return result


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user)):
    return {"conversations": conversations.list_for(user)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID, user: User = Depends(get_current_user)):
    found = conversations.messages(user, str(conversation_id))
    if found is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"messages": found}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: UUID, user: User = Depends(get_current_user)):
    if not conversations.delete(user, str(conversation_id)):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@router.post("/messages/{message_id}/feedback")
def give_feedback(message_id: int, body: Feedback, user: User = Depends(get_current_user)):
    if body.rating not in (1, -1):
        raise HTTPException(status_code=422, detail="Rating must be 1 or -1")
    if not conversations.rate(user, message_id, body.rating, body.comment):
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"status": "recorded"}
