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
EMBEDDING_DIM = 384

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


# General-knowledge path: questions the documents cannot answer, answered by the model alone and labelled as such.
# Company-specific questions are never answered this way (see app/services/question_profile.py).
GENERAL_ENABLED = os.getenv("GENERAL_ENABLED", "true").lower() in ("1", "true", "yes")


def agent_model(name: str) -> str:
    """Model for one agent. Set e.g. VALIDATOR_MODEL=qwen2.5:3b to use a different model for that agent."""
    return os.getenv(f"{name.upper()}_MODEL") or LLM_MODEL

# Uploads are indexed by a background worker. INGEST_ASYNC=false indexes inside the request (small deployments, tests).
INGEST_ASYNC = os.getenv("INGEST_ASYNC", "true").lower() in ("1", "true", "yes")
# true: the web process also runs a worker thread. false: run "python -m scripts.worker" as its own process.
INGEST_WORKER_ENABLED = os.getenv("INGEST_WORKER_ENABLED", "true").lower() in ("1", "true", "yes")
