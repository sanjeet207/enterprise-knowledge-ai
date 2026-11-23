import asyncio
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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


def _prepare(payload: ChatRequest, user: User) -> tuple[Optional[str], list]:
    """Checks that must fail before any answer work starts: rate limit and conversation ownership."""
    if not limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a moment.", headers={"Retry-After": "60"})
    conversation_id = str(payload.conversation_id) if payload.conversation_id else None
    if conversation_id and not conversations.owns(user, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_id, (conversations.recent_questions(conversation_id) if conversation_id else [])


async def _execute(payload: ChatRequest, user: User, conversation_id: Optional[str], previous: list, on_step=None) -> dict:
    question = payload.query
    try:
        if followup.needs_context(question, previous):
            try:
                question = await condenser.run(previous, question)
            except LLMUnavailable:
                question = payload.query  # the normal pipeline below reports the outage
        result = await orchestrator.answer_question(user, question, payload.top_k, retriever, on_step=on_step)
    except LLMUnavailable:
        raise HTTPException(status_code=503, detail="The answer service is unavailable. Try again shortly.")
    metrics.inc("chat_outcomes_total", outcome=result["outcome"])
    if question != payload.query:
        result["corrected_query"] = question
    if not conversation_id:
        conversation_id = conversations.create(user, payload.query)
    result["conversation_id"] = conversation_id
    result["message_id"] = conversations.add_exchange(
        conversation_id, payload.query, result.get("answer") or "", result["outcome"],
        conversations.without_excerpts(result.get("sources")))
    return result


@router.post("/query")
async def rag_query(payload: ChatRequest, user: User = Depends(get_current_user)):
    conversation_id, previous = _prepare(payload, user)
    return await _execute(payload, user, conversation_id, previous)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
async def rag_stream(payload: ChatRequest, user: User = Depends(get_current_user)):
    """Same pipeline and same checks as /chat/query. Progress is sent as each step finishes (step name and time
    only), and the answer is sent once, after it has been verified. Unverified text is never streamed."""
    conversation_id, previous = _prepare(payload, user)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_step(agent: str, ms: int) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("step", {"agent": agent, "ms": ms}))

    async def worker() -> None:
        try:
            await queue.put(("result", await _execute(payload, user, conversation_id, previous, on_step)))
        except HTTPException as exc:
            await queue.put(("error", {"status": exc.status_code, "detail": str(exc.detail)}))
        except Exception:
            await queue.put(("error", {"status": 500, "detail": "Something went wrong. Try again."}))

    async def events():
        task = asyncio.create_task(worker())
        try:
            while True:
                kind, data = await queue.get()
                yield sse(kind, data)
                if kind != "step":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
