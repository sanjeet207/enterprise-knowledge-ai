"""Request IDs, structured (JSON) logs and metrics for every request."""
import json
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from app.services import metrics

logger = logging.getLogger("eka.request")
_SAFE_ID = re.compile(r"^[A-Za-z0-9\-_.]{8,64}$")


def setup_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")  # the interactive API docs load scripts from a CDN


def security_headers(path: str, https: bool) -> dict:
    """Headers that switch off whole classes of browser attacks (framing, sniffing, injected scripts, cached secrets)."""
    headers = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
               "Cross-Origin-Opener-Policy": "same-origin", "Permissions-Policy": "camera=(), microphone=(), geolocation=()"}
    if not path.startswith(_DOC_PATHS):
        headers["Content-Security-Policy"] = _CSP
    if not path.startswith("/static"):
        headers["Cache-Control"] = "no-store"
    if https:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


class RequestMiddleware(BaseHTTPMiddleware):
    """Gives every request an id (a caller's id is kept if it looks safe), times it, logs one JSON line and
    counts it. The line has no names, emails, questions or answers: only ids, route, status and timing."""

    async def dispatch(self, request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
            for name, value in security_headers(request.url.path, https).items():
                response.headers.setdefault(name, value)
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", None) or "unmatched"
            if route not in ("/metrics",):
                metrics.inc("http_requests_total", method=request.method, route=route, status=status)
                metrics.observe(elapsed, route=route)
                logger.info(json.dumps({"event": "request", "request_id": request_id, "method": request.method,
                                        "route": route, "status": status, "ms": round(elapsed * 1000)}))
