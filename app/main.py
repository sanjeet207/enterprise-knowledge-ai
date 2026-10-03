from fastapi import FastAPI

app = FastAPI(
    title="Enterprise Knowledge AI Platform",
    description="Multi-tenant RAG platform with hybrid search and RBAC data isolation",
    version="0.1.0",
)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "enterprise-knowledge-ai"}
