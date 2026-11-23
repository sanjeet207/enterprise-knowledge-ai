from contextlib import asynccontextmanager
from pathlib import Path

import hmac

import psycopg
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import config, observability, tracing
from app.routers import access, admin, documents, retrieval, auth, chat, audit, me, research, sso
from app.services import metrics, startup_guard, worker

STATIC_DIR = Path(__file__).parent / "static"

def _warm_up_models() -> None:
    """Load the search models now (about 10 seconds the first time) instead of during the first question.

    A failure here must never stop the server: the models still load on first use.
    """
    import logging
    log = logging.getLogger("app.warmup")
    try:
        from app.services.embedder import embed_texts
        embed_texts(["warm up"], kind="query")
        from app.services.reranker import rerank_passages
        rerank_passages("warm up", [{"parent_content": "warm up", "parent_id": "0", "document_id": "0", "metadata": {}, "rrf_score": 0.0}], top_k=1)
    except Exception as exc:  # noqa: BLE001
        log.warning("Model warm-up skipped: %s", exc.__class__.__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the upload worker with the server and stop it cleanly on shutdown."""
    startup_guard.check_database(config.DATABASE_URL, config.APP_ENV, config.ALLOW_DEMO_DATA)
    tracing.setup()
    if config.WARM_UP_MODELS:
        _warm_up_models()
    if config.INGEST_WORKER_ENABLED:
        worker.start()
    yield
    worker.stop()
    tracing.shutdown()


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if config.API_DOCS_ENABLED else None,
    redoc_url="/redoc" if config.API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if config.API_DOCS_ENABLED else None,
    title="Enterprise Knowledge AI Platform",
    description="Secure multi-tenant RAG platform with hybrid search, RBAC, and local LLM generation",
    version="0.11.0",
)

observability.setup_logging()
app.add_middleware(observability.RequestMiddleware)

app.include_router(auth.router)
app.include_router(sso.router)
app.include_router(documents.router)
app.include_router(retrieval.router)
app.include_router(chat.router)
app.include_router(research.router)
app.include_router(audit.router)
app.include_router(admin.router)
app.include_router(access.router)
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
