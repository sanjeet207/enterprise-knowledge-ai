from fastapi import FastAPI
from app.routers import documents, retrieval, auth, chat

app = FastAPI(
    title="Enterprise Knowledge AI Platform",
    description="Secure multi-tenant RAG platform with hybrid search, RBAC, and local LLM generation",
    version="0.3.0",
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(retrieval.router)
app.include_router(chat.router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "enterprise-knowledge-ai"}
