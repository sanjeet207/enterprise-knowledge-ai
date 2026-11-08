"""Distributed tracing without a heavy dependency.

Each request, model call, retrieval step and background job becomes a span. Spans are sent in the standard
OTLP/JSON format, so Jaeger, Grafana Tempo, Azure Monitor (via a collector) or any OpenTelemetry backend can show them.

Privacy rule, enforced in code: a span never holds a question, an answer, a document's text, a name or an email.
Only ids, counts, status and timings are accepted (see safe_attributes).

Off by default. Set OTEL_EXPORTER_OTLP_ENDPOINT (for example http://localhost:4318) to send spans,
or OTEL_CONSOLE=true to print them. When off, span() costs almost nothing.
"""
import contextvars
import json
import logging
import os
import queue
import secrets
import threading
import time
from contextlib import contextmanager

from app import config  # noqa: F401 - loads .env before the settings below are read

log = logging.getLogger("eka.tracing")

ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().rstrip("/")
CONSOLE = os.getenv("OTEL_CONSOLE", "false").lower() in ("1", "true", "yes")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "enterprise-knowledge-ai")
HEADERS_RAW = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")

MAX_VALUE_CHARS = 80
MAX_QUEUE = 2000
BATCH = 50
# Attribute names that could carry people's content. Refused whatever the value is.
FORBIDDEN_KEYS = ("question", "answer", "text", "content", "detail", "prompt", "email", "name", "query", "title", "body")

_current: contextvars.ContextVar = contextvars.ContextVar("eka_span", default=None)
_exporter = None


def enabled() -> bool:
    return _exporter is not None


# ---------- pure helpers (unit-tested) ----------

def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def safe_attributes(attrs: dict) -> dict:
    """Keep only plain numbers, booleans and short strings, and drop any key that sounds like content."""
    out = {}
    for key, value in (attrs or {}).items():
        k = str(key).lower()
        if k.split(".")[-1] in FORBIDDEN_KEYS:
            continue
        if isinstance(value, bool) or isinstance(value, (int, float)):
            out[str(key)] = value
        elif isinstance(value, str):
            out[str(key)] = value[:MAX_VALUE_CHARS]
    return out


def parse_headers(raw: str) -> dict:
    """'a=1,b=2' -> {'a': '1', 'b': '2'}. Malformed pairs are skipped."""
    headers = {}
    for pair in (raw or "").split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            if k.strip():
                headers[k.strip()] = v.strip()
    return headers


def attribute_value(value) -> dict:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def span_to_otlp(span: dict) -> dict:
    """One finished span in OTLP/JSON shape."""
    out = {
        "traceId": span["trace_id"], "spanId": span["span_id"], "name": span["name"], "kind": span.get("kind", 1),
        "startTimeUnixNano": str(span["start_ns"]), "endTimeUnixNano": str(span["end_ns"]),
        "attributes": [{"key": k, "value": attribute_value(v)} for k, v in span["attributes"].items()],
        "status": {"code": 2 if span.get("error") else 1},
    }
    if span.get("parent_id"):
        out["parentSpanId"] = span["parent_id"]
    return out


def build_payload(spans: list[dict], service_name: str = SERVICE_NAME) -> dict:
    return {"resourceSpans": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service_name}}]},
        "scopeSpans": [{"scope": {"name": "eka"}, "spans": [span_to_otlp(s) for s in spans]}],
    }]}


# ---------- exporter ----------

class Exporter:
    """Collects finished spans and sends them in batches from a background thread. Never raises into the app."""

    def __init__(self, endpoint: str, console: bool, headers: dict | None = None):
        self.endpoint, self.console, self.headers = endpoint, console, headers or {}
        self.queue: queue.Queue = queue.Queue(maxsize=MAX_QUEUE)
        self.dropped = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="trace-exporter", daemon=True)
        self._thread.start()

    def add(self, span: dict) -> None:
        try:
            self.queue.put_nowait(span)
        except queue.Full:
            self.dropped += 1

    def _drain(self) -> list[dict]:
        batch = []
        while len(batch) < BATCH:
            try:
                batch.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def flush(self) -> None:
        while True:
            batch = self._drain()
            if not batch:
                return
            self._send(batch)

    def _send(self, batch: list[dict]) -> None:
        if self.console:
            for s in batch:
                print(json.dumps({"span": s["name"], "trace": s["trace_id"], "ms": (s["end_ns"] - s["start_ns"]) // 1_000_000,
                                  "attrs": s["attributes"]}), flush=True)
        if not self.endpoint:
            return
        try:
            import httpx
            httpx.post(f"{self.endpoint}/v1/traces", json=build_payload(batch), headers=self.headers, timeout=5.0)
        except Exception as exc:  # noqa: BLE001 - tracing must never break the app
            log.debug("trace export failed: %s", exc.__class__.__name__)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(2.0)
            self.flush()

    def shutdown(self) -> None:
        self._stop.set()
        self.flush()


def setup() -> None:
    global _exporter
    if _exporter is None and (ENDPOINT or CONSOLE):
        _exporter = Exporter(ENDPOINT, CONSOLE, parse_headers(HEADERS_RAW))
        log.info("tracing on (%s)", ENDPOINT or "console")


def shutdown() -> None:
    global _exporter
    if _exporter is not None:
        _exporter.shutdown()
        _exporter = None


# ---------- spans ----------

class Span:
    def __init__(self, name: str, trace_id: str, parent_id: str | None, attrs: dict):
        self.name, self.trace_id, self.parent_id = name, trace_id, parent_id
        self.span_id = new_span_id()
        self.attributes = safe_attributes(attrs)
        self.error = False
        self.start_ns = time.time_ns()
        self._t0 = time.perf_counter()

    def set(self, **attrs) -> None:
        self.attributes.update(safe_attributes(attrs))

    def finish(self, end_ns: int | None = None) -> None:
        if _exporter is None:
            return
        _exporter.add({"trace_id": self.trace_id, "span_id": self.span_id, "parent_id": self.parent_id, "name": self.name,
                       "start_ns": self.start_ns, "end_ns": end_ns or time.time_ns(), "attributes": self.attributes,
                       "error": self.error})


class _NoSpan:
    trace_id = ""
    span_id = ""

    def set(self, **_attrs) -> None:
        pass


_NO_SPAN = _NoSpan()


@contextmanager
def span(name: str, **attrs):
    """Time a block. Nested spans link to their parent automatically, across await points and threads' own contexts."""
    if _exporter is None:
        yield _NO_SPAN
        return
    parent = _current.get()
    s = Span(name, parent.trace_id if parent else new_trace_id(), parent.span_id if parent else None, attrs)
    token = _current.set(s)
    try:
        yield s
    except BaseException:
        s.error = True
        raise
    finally:
        _current.reset(token)
        s.finish()


def record_step(agent: str, started: float) -> None:
    """A span for work that already happened (an agent step): ends now, lasted since 'started' (perf_counter)."""
    if _exporter is None:
        return
    parent = _current.get()
    end = time.time_ns()
    s = Span(f"agent.{agent}", parent.trace_id if parent else new_trace_id(), parent.span_id if parent else None, {"agent": agent})
    s.start_ns = end - int((time.perf_counter() - started) * 1e9)
    s.finish(end)


def current_trace_id() -> str:
    s = _current.get()
    return s.trace_id if s else ""
