from fastapi import FastAPI

from app.routers import auth, documents, retrieval

app = FastAPI(
    title="Enterprise Knowledge AI Platform",
    description="Secure, access-controlled RAG over internal company documents",
    version="0.4.0",
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(retrieval.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "enterprise-knowledge-ai"}
