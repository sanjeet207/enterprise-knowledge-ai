from fastapi import FastAPI
from app.routers import documents, retrieval

app = FastAPI(
    title="Enterprise Knowledge AI Platform",
    description="Multi-tenant pure RAG platform with hybrid search and RBAC data isolation",
    version="0.2.0",
)

app.include_router(documents.router)
app.include_router(retrieval.router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "enterprise-knowledge-ai"}
