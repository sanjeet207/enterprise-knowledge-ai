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
# Hosted models, for deployments (such as Azure) where a local Ollama is not available:
#   LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY, or LLM_PROVIDER=groq + GROQ_API_KEY,
#   or LLM_PROVIDER=openai + LLM_API_KEY + LLM_BASE_URL (any OpenAI-compatible endpoint).
# Then set LLM_MODEL (and optionally <AGENT>_MODEL, ANSWERER_QUICK_MODEL) to that provider's model names.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
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
# answering model (checked by plain code). On by default; it only runs on weak first searches and never changes what the answerer sees. REFINER_ENABLED=false turns it off.
# How the reranker's order is combined with the search order. "rrf" (default) = rank-fuse both orders, so the
# reranker cannot drop a passage the search ranked highly. "none" = rerank order only; "guard" = rerank order, but
# the search's first hit is never dropped. Measured with scripts/retrieval_eval.py (see README).
RERANK_BLEND = os.getenv("RERANK_BLEND", "rrf").lower()

REFINER_ENABLED = os.getenv("REFINER_ENABLED", "true").lower() in ("1", "true", "yes")
# true: every question is rewritten first (its rewrite drives one extra search); false: only after a weak first search.
REFINER_ALWAYS = os.getenv("REFINER_ALWAYS", "true").lower() in ("1", "true", "yes")
# The refiner runs only when the first search scored below this (a clear question with a strong match is left alone),
# and its rewrite is used to search, never shown to the answerer.
# The rewrite only drives a search, so it may reword freely ("holidays" -> "annual leave"); it still may not add or
# drop a number or become an answer. Share of the question's key words that must survive:
REFINER_MIN_OVERLAP = float(os.getenv("REFINER_MIN_OVERLAP", "0.4"))
REFINER_BELOW = float(os.getenv("REFINER_BELOW", "0.5"))
# A smaller answering model is used only when the documents clearly match (top score at least this).
ROUTER_MIN_SCORE = float(os.getenv("ROUTER_MIN_SCORE", "0.9"))

# Off by default: a question the documents cannot answer is refused. Set GENERAL_ENABLED=true to allow labelled general answers.
# General-knowledge path: questions the documents cannot answer, answered by the model alone and labelled as such.
# Company-specific questions are never answered this way (see app/services/question_profile.py).
GENERAL_ENABLED = os.getenv("GENERAL_ENABLED", "false").lower() in ("1", "true", "yes")

# Deeper pass: when the best passages match but the answer model finds them insufficient, search once more, wider
# (more passages from the same access-filtered search, plus everything earlier searches found), and answer again with
# the main model. Every check still applies to that answer. DEEP_SEARCH_ENABLED=false turns it off.
DEEP_SEARCH_ENABLED = os.getenv("DEEP_SEARCH_ENABLED", "true").lower() in ("1", "true", "yes")
DEEP_TOP_K = int(os.getenv("DEEP_TOP_K", "8"))
DEEP_MAX_PASSAGES = int(os.getenv("DEEP_MAX_PASSAGES", "6"))
DEEP_MAX_CHARS = int(os.getenv("DEEP_MAX_CHARS", "8000"))  # keeps the passages inside the model's context window

# Check that every answer (not only a small model's) addresses the question; one that misses the point is written again once.
FIT_CHECK_ALL = os.getenv("FIT_CHECK_ALL", "true").lower() in ("1", "true", "yes")

# Say "not related to company documents" (instead of the generic refusal) for a question that is plainly not about
# the company. Decided from the question alone, by the router, so it never depends on which documents exist.
OFF_TOPIC_NOTICE = os.getenv("OFF_TOPIC_NOTICE", "true").lower() in ("1", "true", "yes")


def answer_model(depth: str) -> str:
    """Model that writes the answer, chosen by how hard the question is (quick, standard, deep).

    Set ANSWERER_QUICK_MODEL=qwen2.5:3b to give short, simple questions to a smaller, faster model. Unset depths use
    the normal answerer model. The validator always uses its own model, so a fast answer is still checked, and an
    answer the small model cannot write or that fails a check is written again by the normal model.
    """
    return os.getenv(f"ANSWERER_{depth.upper()}_MODEL") or agent_model("answerer")


def agent_model(name: str) -> str:
    """Model for one agent. Set e.g. VALIDATOR_MODEL=qwen2.5:3b to use a different model for that agent."""
    return os.getenv(f"{name.upper()}_MODEL") or LLM_MODEL

# Uploads are indexed by a background worker. INGEST_ASYNC=false indexes inside the request (small deployments, tests).
INGEST_ASYNC = os.getenv("INGEST_ASYNC", "true").lower() in ("1", "true", "yes")
# true: the web process also runs a worker thread. false: run "python -m scripts.worker" as its own process.
# Load the embedding and reranking models when the server starts, so the first question is not slow.
WARM_UP_MODELS = os.getenv("WARM_UP_MODELS", "true").lower() in ("1", "true", "yes")
INGEST_WORKER_ENABLED = os.getenv("INGEST_WORKER_ENABLED", "true").lower() in ("1", "true", "yes")

# The highest reading level a portal administrator may grant (separation of duties). Higher levels come from IT security.
ADMIN_MAX_GRANT_LEVEL = max(1, min(4, int(os.getenv("ADMIN_MAX_GRANT_LEVEL", "2"))))

# The interactive API documentation (/docs) is handy locally. Switch it off in production.
API_DOCS_ENABLED = os.getenv("API_DOCS_ENABLED", "true").lower() in ("1", "true", "yes")

# A reviewer model reads each upload for instructions aimed at the assistant (indirect prompt injection).
INSPECT_UPLOADS = os.getenv("INSPECT_UPLOADS", "true").lower() in ("1", "true", "yes")
