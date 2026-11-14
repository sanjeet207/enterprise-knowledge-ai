import os

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


DATABASE_URL = _required("DATABASE_URL")
JWT_SECRET = _required("JWT_SECRET")
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))

# Single sign-on (OpenID Connect, e.g. Microsoft Entra ID). Off unless issuer and client id are set.
# Use a single-tenant issuer such as https://login.microsoftonline.com/<tenant-id>/v2.0
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "").strip()
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "").strip()
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "").strip()
OIDC_REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://127.0.0.1:8000/auth/sso/callback").strip()
OIDC_ENABLED = bool(OIDC_ISSUER and OIDC_CLIENT_ID)
# Turn off to require SSO for everyone (the demo keeps password sign-in on).
PASSWORD_LOGIN_ENABLED = os.getenv("PASSWORD_LOGIN_ENABLED", "true").lower() in ("1", "true", "yes")

# Prometheus /metrics is off unless a token is set.
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
# Audit rows and saved conversations older than this are removed by scripts/purge_retention.py.
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "365"))

# Questions one person may ask per minute (protects the model and the budget).
CHAT_RATE_PER_MINUTE = int(os.getenv("CHAT_RATE_PER_MINUTE", "20"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()  # local | ollama
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# --- LLM and answer-safety settings ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
# Below this top rerank score the question is refused without calling the model.
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "4096"))
REFUSAL_THRESHOLD = float(os.getenv("REFUSAL_THRESHOLD", "0.1"))

# Second-pass check: a separate model call confirms every claim is supported by the sources.
VALIDATOR_ENABLED = os.getenv("VALIDATOR_ENABLED", "true").lower() in ("1", "true", "yes")
VALIDATOR_MAX_RETRIES = int(os.getenv("VALIDATOR_MAX_RETRIES", "2"))

# Planner: bounded tool-calling loop (search or finish). Total searches per question, first one included.
PLANNER_ENABLED = os.getenv("PLANNER_ENABLED", "false").lower() in ("1", "true", "yes")
PLANNER_MAX_SEARCHES = int(os.getenv("PLANNER_MAX_SEARCHES", "3"))


# Refiner: after a question is accepted as being about the company, rewrite it into its clearest form for the
# answering model (checked by plain code). Off until the evaluation shows it helps; REFINER_ENABLED=true turns it on.
# How the reranker's order is combined with the search order. "rrf" (default) = rank-fuse both orders, so the
# reranker cannot drop a passage the search ranked highly. "none" = rerank order only; "guard" = rerank order, but
# the search's first hit is never dropped. Measured with scripts/retrieval_eval.py (see README).
RERANK_BLEND = os.getenv("RERANK_BLEND", "rrf").lower()

REFINER_ENABLED = os.getenv("REFINER_ENABLED", "false").lower() in ("1", "true", "yes")

# Off by default: a question the documents cannot answer is refused. Set GENERAL_ENABLED=true to allow labelled general answers.
# General-knowledge path: questions the documents cannot answer, answered by the model alone and labelled as such.
# Company-specific questions are never answered this way (see app/services/question_profile.py).
GENERAL_ENABLED = os.getenv("GENERAL_ENABLED", "false").lower() in ("1", "true", "yes")


def agent_model(name: str) -> str:
    """Model for one agent. Set e.g. VALIDATOR_MODEL=qwen2.5:3b to use a different model for that agent."""
    return os.getenv(f"{name.upper()}_MODEL") or LLM_MODEL

# Uploads are indexed by a background worker. INGEST_ASYNC=false indexes inside the request (small deployments, tests).
INGEST_ASYNC = os.getenv("INGEST_ASYNC", "true").lower() in ("1", "true", "yes")
# true: the web process also runs a worker thread. false: run "python -m scripts.worker" as its own process.
INGEST_WORKER_ENABLED = os.getenv("INGEST_WORKER_ENABLED", "true").lower() in ("1", "true", "yes")

# The highest reading level a portal administrator may grant (separation of duties). Higher levels come from IT security.
ADMIN_MAX_GRANT_LEVEL = max(1, min(4, int(os.getenv("ADMIN_MAX_GRANT_LEVEL", "2"))))

# The interactive API documentation (/docs) is handy locally. Switch it off in production.
API_DOCS_ENABLED = os.getenv("API_DOCS_ENABLED", "true").lower() in ("1", "true", "yes")

# A reviewer model reads each upload for instructions aimed at the assistant (indirect prompt injection).
INSPECT_UPLOADS = os.getenv("INSPECT_UPLOADS", "true").lower() in ("1", "true", "yes")
