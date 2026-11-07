from pathlib import Path

import hmac

import psycopg
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import config, observability
from app.routers import admin, documents, retrieval, auth, chat, audit, me, sso
from app.services import metrics

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Enterprise Knowledge AI Platform",
    description="Secure multi-tenant RAG platform with hybrid search, RBAC, and local LLM generation",
    version="0.8.0",
)

observability.setup_logging()
app.add_middleware(observability.RequestMiddleware)

app.include_router(auth.router)
app.include_router(sso.router)
app.include_router(documents.router)
app.include_router(retrieval.router)
app.include_router(chat.router)
app.include_router(audit.router)
app.include_router(admin.router)
app.include_router(me.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "enterprise-knowledge-ai"}


@app.get("/ready", tags=["Health"])
def ready():
    """Ready only when the database answers. Use this for load-balancer and container probes."""
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "database unavailable"})
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(authorization: str = Header(default="")):
    """Prometheus text. Off unless METRICS_TOKEN is set; then it needs 'Authorization: Bearer <token>'."""
    if not config.METRICS_TOKEN:
        raise HTTPException(status_code=404)
    if not hmac.compare_digest(authorization, f"Bearer {config.METRICS_TOKEN}"):
        raise HTTPException(status_code=401)
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")
