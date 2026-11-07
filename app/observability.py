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
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", None) or "unmatched"
            if route not in ("/metrics",):
                metrics.inc("http_requests_total", method=request.method, route=route, status=status)
                metrics.observe(elapsed, route=route)
                logger.info(json.dumps({"event": "request", "request_id": request_id, "method": request.method,
                                        "route": route, "status": status, "ms": round(elapsed * 1000)}))
