from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import admin, documents, retrieval, auth, chat, audit

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Enterprise Knowledge AI Platform",
    description="Secure multi-tenant RAG platform with hybrid search, RBAC, and local LLM generation",
    version="0.6.0",
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(retrieval.router)
app.include_router(chat.router)
app.include_router(audit.router)
app.include_router(admin.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "enterprise-knowledge-ai"}
